#!/usr/bin/env python3
"""Merge a run's new articles into news_store.json, archive aged-out entries.

Usage (from the repo root):
  python3 scripts/update_store.py new_articles.json
  python3 scripts/update_store.py --none        # quiet day: no new articles

new_articles.json is a JSON list of objects with: url, title, source,
category, summary, date_published (YYYY-MM-DD). Anything whose normalized URL
is already stored is skipped. Steps (per CLAUDE.md Step 4):
  - back up news_store.json to backups/ before writing
  - append new entries with date_found = today (SGT)
  - recompute is_new_today (date_found == today) on every entry
  - move entries with date_found older than 90 days into news_archive.json
    (with archived_on = today), never deleting without archiving
  - set last_run = now (SGT)
Prints a one-line JSON summary. Exits non-zero without writing on bad input.
"""
import argparse
import glob
import json
import os
import re
import shutil
import sys
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE = os.path.join(ROOT, "news_store.json")
ARCHIVE = os.path.join(ROOT, "news_archive.json")
BACKUPS = os.path.join(ROOT, "backups")
SGT = timezone(timedelta(hours=8))
RETENTION_DAYS = 90

CATEGORIES = {
    "Accidents/Workplace Safety", "Legal & Disputes/Arbitration",
    "Policy/Regulatory", "Project Awards/Tenders",
    "Sustainability/Green Building", "Manpower/Labour",
    "New Technology/Innovation", "Public Feedback/Community",
    "Media Features/Company News", "International/Regional News",
}
FIELDS = ("url", "title", "source", "category", "summary", "date_published")
TRACKING = re.compile(r"^(utm_.*|fbclid|gclid|mc_cid|mc_eid|ref|cid)$", re.I)


def normalize_url(url):
    parts = urlsplit(url.strip())
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                       if not TRACKING.match(k)])
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, query, ""))


def load_store():
    try:
        with open(STORE, encoding="utf-8") as f:
            return json.load(f), None
    except FileNotFoundError:
        return {"schema_version": 1, "last_run": None, "articles": []}, "first run: empty store"
    except json.JSONDecodeError:
        for path in sorted(glob.glob(os.path.join(BACKUPS, "news_store_*.json")), reverse=True):
            try:
                with open(path, encoding="utf-8") as f:
                    return json.load(f), f"store was corrupt; restored from {os.path.basename(path)}"
            except (OSError, json.JSONDecodeError):
                continue
        sys.exit("news_store.json is corrupt and no readable backup exists; stopping")


def validate(new):
    if not isinstance(new, list):
        sys.exit("new articles file must contain a JSON list")
    for i, a in enumerate(new):
        missing = [k for k in FIELDS if not a.get(k)]
        if missing:
            sys.exit(f"article {i} missing {missing}")
        if a["category"] not in CATEGORIES:
            sys.exit(f"article {i} has unknown category {a['category']!r}")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", a["date_published"]):
            sys.exit(f"article {i} date_published must be YYYY-MM-DD")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("new_articles", nargs="?")
    ap.add_argument("--none", action="store_true", help="quiet day, no new articles")
    ap.add_argument("--now", help="override current time (ISO, for testing)")
    args = ap.parse_args()
    if not args.new_articles and not args.none:
        ap.error("pass a new-articles file or --none")

    now = datetime.fromisoformat(args.now) if args.now else datetime.now(SGT)
    now = now.astimezone(SGT).replace(microsecond=0)
    today = now.date().isoformat()

    new = []
    if args.new_articles:
        with open(args.new_articles, encoding="utf-8") as f:
            new = json.load(f)
        validate(new)

    store, note = load_store()
    articles = store.get("articles", [])
    known = {normalize_url(a["url"]) for a in articles}

    if os.path.exists(STORE) and not (note or "").startswith("store was corrupt"):
        os.makedirs(BACKUPS, exist_ok=True)
        shutil.copy2(STORE, os.path.join(BACKUPS, f"news_store_{now:%Y%m%d_%H%M%S}.json"))

    added, skipped = [], []
    for a in new:
        key = normalize_url(a["url"])
        if key in known:
            skipped.append(a["url"])
            continue
        known.add(key)
        entry = {k: a[k].strip() for k in FIELDS}
        entry["date_found"] = today
        articles.append(entry)
        added.append(entry)

    cutoff = (now.date() - timedelta(days=RETENTION_DAYS)).isoformat()
    keep, aged = [], []
    for a in articles:
        (aged if a["date_found"] < cutoff else keep).append(a)
    for a in keep:
        a["is_new_today"] = a["date_found"] == today

    if aged:
        try:
            with open(ARCHIVE, encoding="utf-8") as f:
                archive = json.load(f)
        except FileNotFoundError:
            archive = {"schema_version": 1, "articles": []}
        archived = {normalize_url(r["url"]) for r in archive["articles"]}
        for a in aged:
            if normalize_url(a["url"]) in archived:
                continue
            rec = {k: v for k, v in a.items() if k != "is_new_today"}
            rec["archived_on"] = today
            archive["articles"].append(rec)
        with open(ARCHIVE, "w", encoding="utf-8") as f:
            json.dump(archive, f, ensure_ascii=False, indent=2)
            f.write("\n")

    store = {"schema_version": 1, "last_run": now.isoformat(), "articles": keep}
    with open(STORE, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
        f.write("\n")

    counts = {}
    for a in added:
        counts[a["category"]] = counts.get(a["category"], 0) + 1
    print(json.dumps({
        "today": today, "added": len(added), "added_by_category": counts,
        "skipped_duplicates": skipped, "archived": len(aged),
        "total": len(keep), "note": note,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
