# Construction News Agent (Singapore)

A daily automated digest of Singapore construction-industry news. A scheduled
Claude cloud routine searches the web every morning, classifies what it finds
into fixed categories, and keeps a dashboard up to date at a stable URL —
plus a short push notification each day.

## What this is (and isn't)

- **Not an installed app.** There's no server or database to run.
- **It runs in the cloud, not on this PC.** The routine (`construction-news-agent`)
  is a scheduled Claude cloud session, not a local cron job — each fire spins up
  a fresh sandbox that clones this repo, does the day's work, commits the
  updated files back, and publishes the dashboard. Its full instructions are
  stored as the routine's own prompt (view/edit via the `schedule` skill or
  the routines list at claude.ai/code/routines), not as a file in this repo.
- **This repo is both the routine's input and its output** — the cloned
  starting state each morning, and where it commits the day's results:
  - [`news_store.json`](news_store.json) — active article store (dedup key: normalized URL), 90-day retention
  - [`news_archive.json`](news_archive.json) — permanent history of every article that has ever aged out of the active store (see below)
  - `dashboard.html` — source for the published Artifact dashboard (regenerated daily from `news_store.json` only)
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
reweight a source, edit the routine's prompt (via the `schedule` skill) —
its "Gather candidates" step lists the search queries.

## History / retention

- **`news_store.json`** (active, drives the dashboard): an article is kept
  for 90 days from the day it was first found (`date_found`). `is_new_today`
  is recomputed every run and is not a permanent flag.
- **`news_archive.json`** (permanent, does not drive the dashboard): the
  moment an article would otherwise be dropped from `news_store.json` for
  being past 90 days, it's appended here first — same per-article shape, plus
  an `archived_on` date — so nothing found by the agent is ever truly lost,
  it just stops appearing on the live dashboard. This file only grows; nothing
  reads it back into the active store automatically.

## Troubleshooting

- **Dashboard didn't update / notification says a run failed:** check that
  `news_store.json` is valid JSON. If corrupted, the routine restores from
  the latest file in `backups/` automatically; if that also fails it stops
  and notifies rather than silently resetting.
- **Duplicate articles appearing:** dedup is keyed on a normalized URL
  (scheme+host lowercased, tracking params/fragment/trailing slash
  stripped). If a source changes its URL format across visits, dedup can
  miss — worth a note in the routine's prompt if it recurs.
- **Looking for an old story no longer on the dashboard:** check
  `news_archive.json` — it's kept indefinitely even after the 90-day window
  on the live store.
- **Want to re-run manually, check its logs, or edit its prompt:** use the
  `schedule` skill, or the routines list at claude.ai/code/routines.
