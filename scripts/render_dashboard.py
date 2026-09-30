#!/usr/bin/env python3
"""Render dashboard.html from news_store.json using scripts/dashboard_template.html.

The template holds all page chrome (styles, search bar, controls-bar, Archive
button, collapse script). This script only fills in the stats, last-run time,
category legend and category sections, so the chrome can never be dropped.

Usage: python3 scripts/render_dashboard.py   (run from the repo root)
"""
import html
import json
import os
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(ROOT, "scripts", "dashboard_template.html")
STORE = os.path.join(ROOT, "news_store.json")
OUT = os.path.join(ROOT, "dashboard.html")

CATEGORIES = [
    "Accidents/Workplace Safety",
    "Legal & Disputes/Arbitration",
    "Policy/Regulatory",
    "Project Awards/Tenders",
    "Sustainability/Green Building",
    "Manpower/Labour",
    "New Technology/Innovation",
    "Public Feedback/Community",
    "Media Features/Company News",
    "International/Regional News",
]


def esc(text):
    return html.escape(text or "", quote=True)


def fmt_last_run(value):
    if not value:
        return "never"
    dt = datetime.fromisoformat(value)
    hour = dt.strftime("%I").lstrip("0")
    return f"{dt.day} {dt.strftime('%b %Y')}, {hour}:{dt.strftime('%M %p')} SGT"


def card(a):
    cls = "card is-new" if a.get("is_new_today") else "card"
    badge = '<span class="badge-new">NEW</span>' if a.get("is_new_today") else ""
    return (
        f'        <article class="{cls}">\n'
        f'          <div class="card-top">{badge}<span class="source">{esc(a["source"])}</span>'
        f'<span class="dot">&middot;</span><span class="date">{esc(a["date_published"])}</span></div>\n'
        f'          <h3><a href="{esc(a["url"])}" target="_blank" rel="noopener">{esc(a["title"])}</a></h3>\n'
        f'          <p>{esc(a["summary"])}</p>\n'
        f'        </article>'
    )


def main():
    with open(STORE, encoding="utf-8") as f:
        store = json.load(f)
    articles = store.get("articles", [])

    unknown = {a["category"] for a in articles} - set(CATEGORIES)
    if unknown:
        raise SystemExit(f"Unknown categories in store: {sorted(unknown)}")

    by_cat = {c: [] for c in CATEGORIES}
    for a in articles:
        by_cat[a["category"]].append(a)
    for items in by_cat.values():
        # Newest date_published first; stable sort keeps store order for ties.
        items.sort(key=lambda a: a["date_published"], reverse=True)

    new_count = sum(1 for a in articles if a.get("is_new_today"))
    stats = "\n".join([
        f'      <div class="stat"><span class="n">{len(articles)}</span><span class="l">Total stories</span></div>',
        f'      <div class="stat"><span class="n">{new_count}</span><span class="l">New today</span></div>',
        f'      <div class="stat"><span class="n">{len(CATEGORIES)}</span><span class="l">Categories</span></div>',
    ])

    legend, sections = [], []
    for i, cat in enumerate(CATEGORIES, 1):
        items = by_cat[cat]
        rank = f"{i:02d}"
        legend.append(
            f'    <a href="#cat-{i}"><span class="rank">{rank}</span>{esc(cat)}'
            f'<span class="count">{len(items)}</span></a>'
        )
        label = "1 story" if len(items) == 1 else f"{len(items)} stories"
        head = (
            f'    <section class="category" id="cat-{i}">\n'
            f'      <div class="cat-head"><span class="rank">{rank}</span><h2>{esc(cat)}</h2>'
            f'<span class="count">{label}</span></div>\n'
        )
        if items:
            body = '      <div class="cards">\n' + "\n".join(card(a) for a in items) + "\n      </div>\n"
        else:
            body = '      <div class="empty-panel">No stories in this category yet.</div>\n'
        sections.append(head + body + "    </section>\n")

    with open(TEMPLATE, encoding="utf-8") as f:
        page = f.read()
    page = (page.replace("{{STATS}}", stats)
                .replace("{{LAST_RUN}}", fmt_last_run(store.get("last_run")))
                .replace("{{LEGEND}}", "\n".join(legend))
                .replace("{{SECTIONS}}", "\n".join(sections).rstrip("\n") + "\n"))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"dashboard.html: {len(articles)} stories, {new_count} new")


if __name__ == "__main__":
    main()
