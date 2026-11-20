#!/usr/bin/env python3
"""Fetch the feed/listing sources for Step 1 and print only fresh candidates.

Replaces reading raw RSS/HTML into the conversation. One command fetches:
Straits Times RSS, Business Times RSS, the ST MND tag page, the LTA newsroom
listing, MND speeches + press releases (via MND's Directus API), the MOM
(Ministry of Manpower) press-releases listing, the BCA newsroom RSS,
Shimizu Corporation's English "News & Information" listing, UOL Group's
press-releases listing, and the CapitaLand newsroom (via its listing API). It keeps items inside the date
window whose URL is not already in news_store.json or news_archive.json,
applies a loose construction-relevance keyword filter (the model still makes
the final call), and prints one line per candidate.

Usage (from the repo root):
  python3 scripts/fetch_sources.py [--days 14]
      -> candidate list, one line each: [source] date | title | url
  python3 scripts/fetch_sources.py text URL [--chars 6000]
      -> plain text of one article (works for straitstimes.com, which
         WebFetch refuses, and for MND pages via the API)
"""
import argparse
import html
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from update_store import normalize_url  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SGT = timezone(timedelta(hours=8))
UA = "Mozilla/5.0 (compatible; construction-news-agent)"
# Hosts behind Cloudflare bot rules that 403 the bot UA but serve a normal browser UA.
BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
BROWSER_UA_HOSTS = ("www.uol.com.sg",)

ST_RSS = "https://www.straitstimes.com/news/singapore/rss.xml"
BT_RSS = "https://www.businesstimes.com.sg/rss.xml"
ST_MND_TAG = "https://www.straitstimes.com/tags/ministry-of-national-development?ref=see-more-on"
LTA_LIST = "https://www.lta.gov.sg/content/ltagov/en/newsroom.html"
MND_API = "https://www.mnd.gov.sg/api/articles"
MOM_LIST = "https://www.mom.gov.sg/newsroom/press-releases"
BCA_RSS = "https://www1.bca.gov.sg/resources/newsroom/rss.xml"
SHIMIZU_LIST = "https://www.shimz.co.jp/en/information/"
UOL_LIST = "https://www.uol.com.sg/investors-and-media/press-releases/"
# CapitaLand's newsroom page fills its list client-side from this AEM endpoint
# (selectors copied from the page's JS; {years} = "<last year>-<this year>").
CAPITALAND_API = ("https://www.capitaland.com/api-v1/capitaland/newslisting.listFrom.tags"
                  ".parentPages./content/capitaland/global/en/about-capitaland/newsroom/news-releases/international"
                  ".preTags.capitaland:international-newsroom.tagsMatch.any.year.{years}"
                  ".orderBy.newest.sortOrder.desc.page.1.limit.20"
                  ".currentPath./content/capitaland/global/en/about-capitaland/newsroom.language.en.json")
# Mall promotions, festive campaigns, Ascott lodging, overseas-trust results and
# routine REIT business updates / credit ratings: not construction news.
CAPITALAND_SKIP = re.compile(r"(Starbucks|Bearista|STAR\$|Christmas|festive|Lunar New Year|Hari Raya|"
                             r"Deepavali|giveaway|Ascott|lyf |CFC|shopping|dining|concert|"
                             r"(China|India|Malaysia) Trust|Business Updates|Fitch|Moody|S&P|rating)", re.I)
MND_TYPES = {
    "speeches": "e45b3aaf-3de0-4c98-922a-d5ad73ab5c0b",
    "press-releases": "bcb1e98c-5a6c-4f76-a93a-6c263b9aecda",
}
WATCHLIST = [
    "Wee Hur", "BRC Asia", "Lian Beng", "Koh Brothers", "Hock Lian Seng",
    "CSC Holdings", "Chip Eng Seng", "UOL", "CapitaLand", "City Developments",
    "CDL", "Tiong Seng", "BBR", "Hwa Seng", "Kajima", "Shimizu", "JTC", "Kok Tong", "KTC",
    "The GEAR", "Pan-United", "Continental Steel",
    "HSC Pipeline", "DLM", "DLE",
]
KEYWORDS = [
    r"construct", r"built environment", r"building", r"contractor", r"developer",
    r"tender", r"contract", r"award", r"BTO", r"HDB", r"URA", r"BCA", r"MND",
    r"MOM", r"worksite", r"work site", r"workplace", r"dormitor", r"infrastructure",
    r"MRT", r"LTA", r"tunnel", r"viaduct", r"bridge", r"expressway", r"property",
    r"land", r"GLS", r"en bloc", r"en-bloc", r"housing", r"flats?", r"estate",
    r"redevelop", r"crane", r"scaffold", r"excavat", r"piling", r"concrete",
    r"cement", r"steel", r"rebar", r"sand", r"data cent", r"fab", r"plant",
    r"facility", r"groundbreak", r"Green Mark", r"net.zero", r"carbon", r"prefab",
    r"PPVC", r"DfMA", r"BIM", r"robot", r"automat", r"heat stress", r"safety",
    r"accident", r"fatal", r"dies", r"died", r"injur", r"collapse", r"arbitrat",
    r"lawsuit", r"sued", r"dispute", r"insolven", r"liquidat", r"terminal",
    r"airport", r"Changi", r"engineer", r"architect", r"renovat", r"workers?",
    r"energy", r"electricity", r"biomethane", r"solar", r"natural gas", r"carbon tax",
] + [re.escape(w) for w in WATCHLIST]
RELEVANT = re.compile(r"\b(" + "|".join(KEYWORDS) + r")", re.I)
LTA_SKIP = re.compile(r"\b(fare|ERP|COE|bus (services?|routes?|interchange|connectivity)|taxi|private.hire|"
                      r"licen[cs]|vehicle quota|PMD|e-scooter|motorcycl|parking)", re.I)
# MOM titles rarely say "construction" even when the release is about construction
# firms/workers (work-pass fraud, dormitories, heat stress), so MOM items skip the
# keyword filter; only clearly non-construction statistics/wage/ASEAN items are dropped.
MOM_SKIP = re.compile(r"(labour market|wages? council|NWC|statistician|CPF contribution rate|"
                      r"retrenchment|unemployment|job vacanc|mental well-being)", re.I)


def get_bytes(url, timeout=60):
    browser = urllib.parse.urlparse(url).hostname in BROWSER_UA_HOSTS
    headers = {"User-Agent": BROWSER_UA if browser else UA}
    if browser:
        headers.update({"Accept": "text/html,application/pdf,*/*", "Accept-Language": "en"})
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def get(url, timeout=60):
    return get_bytes(url, timeout).decode("utf-8", "replace")


def pdf_text(data):
    try:  # poppler's pdftotext if installed, else pypdf
        return subprocess.run(["pdftotext", "-layout", "-", "-"], input=data,
                              capture_output=True, check=True, timeout=60).stdout.decode("utf-8", "replace")
    except (OSError, subprocess.SubprocessError):
        import io
        from pypdf import PdfReader
        return "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(data)).pages)


def clean(text):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()


def rss(url, label):
    out = []
    for item in re.findall(r"<item>(.*?)</item>", get(url), re.S):
        def tag(name):
            m = re.search(rf"<{name}[^>]*>(.*?)</{name}>", item, re.S)
            return clean(re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", m.group(1), flags=re.S)) if m else ""
        try:
            date = parsedate_to_datetime(tag("pubDate")).astimezone(SGT).date()
        except (TypeError, ValueError):
            date = None
        out.append({"src": label, "date": date, "title": tag("title"),
                    "url": tag("link"), "blurb": tag("description")})
    return out


def st_mnd_tag():
    page = get(ST_MND_TAG)
    out, seen = [], set()
    for m in re.finditer(r'<a href="(/singapore/[^"#?]+)"[^>]*>(.*?)</a>', page, re.S):
        path, title = m.group(1), clean(m.group(2))
        if path in seen or len(title) < 15:
            continue
        seen.add(path)
        # Embedded page data lists: "title","/path","updatedDate","publishedDate"
        date = None
        d = re.search(re.escape(path) + r'\\",\\"[\d\-T:.]+Z\\",\\"([\d\-T:.]+Z)', page)
        if d:
            date = datetime.fromisoformat(d.group(1).replace("Z", "+00:00")).astimezone(SGT).date()
        out.append({"src": "ST-MND-tag", "date": date, "title": title,
                    "url": "https://www.straitstimes.com" + path, "blurb": ""})
    return out


def lta():
    out = []
    for block in re.findall(r'<li class="item">(.*?)</li>', get(LTA_LIST, timeout=120), re.S):
        a = re.search(r'<h5 class="mt-3 title"><a href="([^"]+)">(.*?)</a>', block, re.S)
        d = re.search(r'<span class="date"[^>]*>(\d{4}-\d{2}-\d{2})</span>', block)
        if not a or not d:
            continue
        label = re.search(r'<div class="label[^"]*">(.*?)</div>', block, re.S)
        if not label or clean(label.group(1)) != "News Releases":
            continue  # user wants News Releases only, not Media Replies
        blurb = re.search(r'<p class="news-paragraph">(.*?)</p>', block, re.S)
        out.append({"src": "LTA",
                    "date": datetime.strptime(d.group(1), "%Y-%m-%d").date(),
                    "title": clean(a.group(2)),
                    "url": urllib.parse.urljoin("https://www.lta.gov.sg", a.group(1)),
                    "blurb": clean(blurb.group(1)) if blurb else ""})
    return out


def mom(max_pages=3):
    out = []
    for page in range(1, max_pages + 1):
        url = MOM_LIST if page == 1 else f"{MOM_LIST}?page={page}"
        for block in re.findall(r"<article>(.*?)</article>", get(url, timeout=90), re.S):
            a = re.search(r'<h3 class="item-title">\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block, re.S)
            d = re.search(r'<time datetime="(\d{4})-(\d{1,2})-(\d{1,2})"', block)
            if not a or not d:
                continue
            out.append({"src": "MOM",
                        "date": datetime(int(d.group(1)), int(d.group(2)), int(d.group(3))).date(),
                        "title": clean(a.group(2)),
                        "url": urllib.parse.urljoin("https://www.mom.gov.sg", a.group(1)),
                        "blurb": ""})
    return out


def shimizu():
    # Server-rendered "Latest News" tab: <div class="date">Month D, YYYY</div> ...
    # <div class="text"><a href="/en/...">title</a>. Covers news releases AND the
    # /en/information/others/ items (e.g. the 2026-11-19 Singapore co-creation
    # centre) that search engines index late or never.
    out, seen = [], set()
    page = get(SHIMIZU_LIST, timeout=60)
    for block in re.findall(r"<li>\s*(<div class=\"date\">.*?)</li>", page, re.S):
        d = re.search(r'<div class="date">\s*([A-Za-z]+ \d{1,2}, \d{4})\s*</div>', block)
        a = re.search(r'<div class="text">\s*<a href="([^"]+)"[^>]*>(.*?)</a>', block, re.S)
        if not d or not a:
            continue
        url = urllib.parse.urljoin("https://www.shimz.co.jp", a.group(1))
        if url in seen or url.lower().endswith(".pdf"):
            continue
        seen.add(url)
        try:
            date = datetime.strptime(d.group(1), "%B %d, %Y").date()
        except ValueError:
            date = None
        out.append({"src": "Shimizu", "date": date, "title": clean(a.group(2)),
                    "url": url, "blurb": ""})
    return out


def uol():
    # <li class="boxes" data-year="YYYY"><a href="...pdf"><h3>Month D, YYYY</h3><p>title</p></a>
    # Releases are PDFs; `text URL` extracts them. Cloudflare: needs BROWSER_UA.
    out = []
    for href, d, title in re.findall(
            r'<li class="boxes"[^>]*>\s*<a href="([^"]+)"[^>]*>\s*<h3>([^<]+)</h3>\s*<p>(.*?)</p>',
            get(UOL_LIST), re.S):
        try:
            date = datetime.strptime(clean(d), "%B %d, %Y").date()
        except ValueError:
            date = None
        out.append({"src": "UOL", "date": date, "title": clean(title),
                    "url": urllib.parse.urljoin(UOL_LIST, href), "blurb": ""})
    return out


def capitaland():
    years = f"{datetime.now(SGT).year - 1}-{datetime.now(SGT).year}"
    out = []
    for r in json.loads(get(CAPITALAND_API.format(years=years)))["data"]:
        try:
            date = datetime.strptime(r["publishedDate"], "%d %b %Y").date()
        except (KeyError, ValueError):
            date = None
        path = r.get("url", "").replace("/content/capitaland/global/en/", "/en/", 1)
        out.append({"src": "CapitaLand", "date": date, "title": clean(r.get("title", "")),
                    "url": urllib.parse.urljoin("https://www.capitaland.com", path), "blurb": ""})
    return out


def mnd_query(params):
    return json.loads(get(MND_API + "?" + urllib.parse.urlencode(params)))["data"]


def mnd():
    out = []
    for kind, type_id in MND_TYPES.items():
        rows = mnd_query({
            "filter[_and][0][status][_eq]": "published",
            "filter[_and][1][article_type][_eq]": type_id,
            "sort": "-article_date_time", "limit": "15",
            "fields": "title,url,article_date_time",
        })
        for r in rows:
            dt = datetime.fromisoformat(r["article_date_time"].replace("Z", "+00:00"))
            out.append({"src": "MND " + kind, "date": dt.astimezone(SGT).date(),
                        "title": clean(r["title"]),
                        "url": f"https://www.mnd.gov.sg/newsroom/{kind}/view/{r['url']}",
                        "blurb": ""})
    return out


def known_urls():
    urls = set()
    for name in ("news_store.json", "news_archive.json"):
        try:
            with open(os.path.join(ROOT, name), encoding="utf-8") as f:
                urls |= {normalize_url(a["url"]) for a in json.load(f).get("articles", [])}
        except (OSError, ValueError):
            pass
    return urls


def list_candidates(days):
    cutoff = datetime.now(SGT).date() - timedelta(days=days)
    known = known_urls()
    sources = [
        ("ST RSS", lambda: rss(ST_RSS, "ST")), ("BT RSS", lambda: rss(BT_RSS, "BT")),
        ("ST MND tag", st_mnd_tag), ("LTA", lta), ("MND", mnd), ("MOM", mom),
        ("BCA RSS", lambda: rss(BCA_RSS, "BCA")), ("Shimizu", shimizu), ("UOL", uol),
        ("CapitaLand", capitaland),
    ]
    lines, stats, errors = [], [], []
    for name, fn in sources:
        try:
            items = fn()
        except Exception as e:  # keep going: one bad source must not stop the run
            errors.append(f"{name}: {type(e).__name__}: {e}")
            continue
        kept = 0
        for it in items:
            if not it["url"] or normalize_url(it["url"]) in known:
                continue
            if it["date"] and it["date"] < cutoff:
                continue
            text = it["title"] + " " + it["blurb"]
            if it["src"] == "CapitaLand" and CAPITALAND_SKIP.search(it["title"]):
                continue
            # MND, BCA, Shimizu, UOL and CapitaLand items skip the keyword filter: BCA is the
            # regulator, and the watchlist firms' titles rarely say "Singapore" or
            # "construction" (the model applies the SG test and judges relevance).
            is_mnd = it["src"].startswith(("MND", "ST-MND", "BCA", "Shimizu", "UOL", "CapitaLand"))
            is_mom = it["src"] == "MOM"
            if is_mom and MOM_SKIP.search(it["title"]):
                continue
            if not is_mnd and not is_mom and not RELEVANT.search(text):
                continue
            if it["src"].startswith("LTA") and LTA_SKIP.search(it["title"]):
                continue
            kept += 1
            date = it["date"].isoformat() if it["date"] else "????-??-??"
            lines.append(f"[{it['src']}] {date} | {it['title']} | {it['url']}")
        stats.append(f"{name} {kept}/{len(items)}")
    print(f"# window: since {cutoff} | kept/fetched: " + ", ".join(stats))
    for e in errors:
        print(f"# ERROR {e}")
    print("\n".join(lines) if lines else "# no new candidates")


def article_text(url, chars):
    m = re.match(r"https?://www\.mnd\.gov\.sg/newsroom/[^/]+/view/([^/?#]+)", url)
    if m:
        rows = mnd_query({
            "filter[_and][0][status][_eq]": "published",
            "filter[_and][1][url][_eq]": m.group(1), "fields": "*,title.*",
        })
        body = rows[0].get("content", "") if rows else ""
    elif urllib.parse.urlparse(url).path.lower().endswith(".pdf"):
        print(re.sub(r"[ \t]+", " ", pdf_text(get_bytes(url))).strip()[:chars])
        return
    else:
        body = get(url)
        body = re.sub(r"<(script|style|noscript|svg|nav|header|footer)[^>]*>.*?</\1>", " ", body, flags=re.S | re.I)
        paras = re.findall(r"<p[^>]*>(.*?)</p>", body, re.S)
        if sum(len(p) for p in paras) > 500:
            body = "\n".join(paras)
    text = clean(body)
    print(text[:chars] + (" …[truncated]" if len(text) > chars else ""))


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "searches":
        print(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "searches.txt")).read())
        return
    if len(sys.argv) > 1 and sys.argv[1] == "text":
        ap = argparse.ArgumentParser(prog="fetch_sources.py text")
        ap.add_argument("url")
        ap.add_argument("--chars", type=int, default=6000)
        a = ap.parse_args(sys.argv[2:])
        article_text(a.url, a.chars)
        return
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=14, help="date window (default 14)")
    list_candidates(ap.parse_args().days)


if __name__ == "__main__":
    main()
