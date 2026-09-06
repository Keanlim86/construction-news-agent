# Construction News Agent (Singapore)

A daily automated digest of Singapore construction-industry news. A scheduled
Claude agent searches the web every morning, classifies what it finds into
fixed categories, and keeps a dashboard up to date at a stable URL — plus a
short push notification each day.

## What this is (and isn't)

- **Not an installed app.** There's no server or database to run. It's a
  scheduled routine (a cron-triggered Claude agent) that reads/writes files
  in this folder and republishes one web page.
- **The routine's instructions** live at
  `C:\Users\USER\.claude\scheduled-tasks\construction-news-agent\SKILL.md`
  (edited via the `schedule` skill, not this folder).
- **This folder** holds the data and output:
  - [`news_store.json`](news_store.json) — persistent article store (dedup key: normalized URL)
  - `dashboard.html` — source for the published Artifact dashboard (regenerated daily)
  - `backups/` — timestamped snapshot of `news_store.json` before each overwrite
  - `CLAUDE.md` — the original design/implementation plan this project was built from

## Schedule

Runs daily at **7:00 AM Singapore time (UTC+8)**, i.e. 23:00 UTC the
previous day.

## The 10 categories (priority order when an article touches more than one)

Categories 1–9 cover Singapore construction/built-environment news; category
10 is a separate bucket for major international/regional industry news with
no direct Singapore link.

1. Accidents/Workplace Safety
2. Legal & Disputes/Arbitration
3. Policy/Regulatory
4. Project Awards/Tenders
5. Sustainability/Green Building
6. Manpower/Labour
7. New Technology/Innovation
8. Public Feedback/Community
9. Media Features/Company News (default bucket for Singapore stories)
10. International/Regional News (major global/regional stories — e.g. a large
    developer's insolvency or a private-credit fund's exposure — sourced
    mainly via Bloomberg; kept to a high bar, not a catch-all)

Articles that are neither about Singapore nor a major international/regional
story clearing category 10's bar are discarded rather than force-fit into a
category.

## Adjusting sources

The routine searches a default set of Singapore sources (Straits Times,
Business Times, CNA, BCA newsroom, HDB/URA press releases, Construction Plus
Asia, and similar) plus Bloomberg for international/regional stories, via
`WebSearch`/`WebFetch`, not fixed per-site scrapers. To add, remove, or
reweight a source, edit the search queries in `SKILL.md`'s "Gather
candidates" step.

## History / retention

Articles are kept for 90 days from the day they were first found
(`date_found`), then dropped from the store and dashboard. `is_new_today` is
recomputed every run and is not a permanent flag.

## Troubleshooting

- **Dashboard didn't update / notification says a run failed:** check that
  `news_store.json` is valid JSON. If corrupted, the routine restores from
  the latest file in `backups/` automatically; if that also fails it stops
  and notifies rather than silently resetting.
- **Duplicate articles appearing:** dedup is keyed on a normalized URL
  (scheme+host lowercased, tracking params/fragment/trailing slash
  stripped). If a source changes its URL format across visits, dedup can
  miss — worth a note in `SKILL.md` if it recurs.
- **Want to re-run manually:** trigger the `construction-news-agent`
  scheduled task via the `schedule` skill/tooling rather than editing files
  by hand.
