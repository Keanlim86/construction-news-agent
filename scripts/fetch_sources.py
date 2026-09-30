#!/usr/bin/env python3
"""Fetch the feed/listing sources for Step 1 and print only fresh candidates.

Replaces reading raw RSS/HTML into the conversation. One command fetches:
Straits Times RSS, Business Times RSS, the ST MND tag page, the LTA newsroom
listing, and MND speeches + press releases (via MND's Directus API). It keeps
items inside the date window whose URL is not already in news_store.json or
news_archive.json, applies a loose construction-relevance keyword filter
(the model still makes the final call), and prints one line per candidate.

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

ST_RSS = "https://www.straitstimes.com/news/singapore/rss.xml"
BT_RSS = "https://www.businesstimes.com.sg/rss.xml"
ST_MND_TAG = "https://www.straitstimes.com/tags/ministry-of-national-development?ref=see-more-on"
LTA_LIST = "https://www.lta.gov.sg/content/ltagov/en/newsroom.html"
MND_API = "https://www.mnd.gov.sg/api/articles"
MND_TYPES = {
    "speeches": "e45b3aaf-3de0-4c98-922a-d5ad73ab5c0b",
    "press-releases": "bcb1e98c-5a6c-4f76-a93a-6c263b9aecda",
}
WATCHLIST = [
    "Wee Hur", "BRC Asia", "Lian Beng", "Koh Brothers", "Hock Lian Seng",
    "CSC Holdings", "Chip Eng Seng", "UOL", "CapitaLand", "City Developments",
    "CDL", "Tiong Seng", "BBR", "Hwa Seng", "Kajima", "JTC", "Kok Tong", "KTC",
    "The GEAR", "Pan-United", "Continental Steel",
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
] + [re.escape(w) for w in WATCHLIST]
RELEVANT = re.compile(r"\b(" + "|".join(KEYWORDS) + r")", re.I)
LTA_SKIP = re.compile(r"\b(fare|ERP|COE|bus (services?|routes?|interchange|connectivity)|taxi|private.hire|"
                      r"licen[cs]|vehicle quota|PMD|e-scooter|motorcycl|parking)", re.I)


def get(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


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
        ("ST MND tag", st_mnd_tag), ("LTA", lta), ("MND", mnd),
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
            is_mnd = it["src"].startswith(("MND", "ST-MND"))
            if not is_mnd and not RELEVANT.search(text):
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
    else:
        body = get(url)
        body = re.sub(r"<(script|style|noscript|svg|nav|header|footer)[^>]*>.*?</\1>", " ", body, flags=re.S | re.I)
        paras = re.findall(r"<p[^>]*>(.*?)</p>", body, re.S)
        if sum(len(p) for p in paras) > 500:
            body = "\n".join(paras)
    text = clean(body)
    print(text[:chars] + (" …[truncated]" if len(text) > chars else ""))


def main():
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
