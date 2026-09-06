# Construction News Agent (Singapore) — Daily Scheduled Digest

> Status: **Planned, not yet built.** This file is the approved implementation
> plan. Open a Claude Code session in this folder and say something like
> "build the construction news agent per CLAUDE.md" to resume/execute it.

## Context

The user wants a daily agent that scrapes/searches the web for Singapore
construction-industry news — project awards, new technology, media features,
public feedback, accidents, and related categories — and surfaces it as an
organized, always-up-to-date view. This is a standalone project, unrelated to
the sibling "Judiciary Hearing List" project in the parent folder (that
project's scraper.py/update_hearing_list.py were reviewed only for reusable
patterns — URL-keyed dedup, backup-before-overwrite, incremental merge — not
directly reusable code, since that project scrapes one structured API while
this one aggregates many news sources via search).

Confirmed with the user:
- **Scope**: Singapore-focused construction industry news.
- **Sourcing**: Web search + RSS/press-release pages across a default set of
  SG sources (Straits Times, Business Times, CNA, BCA newsroom, HDB/URA press
  releases, Construction Plus Asia, and similar), refined over time — not
  fixed per-site HTML scrapers.
- **Categorization**: The scheduled Claude agent itself reads and classifies
  each article (no separate classifier/API) into 9 fixed categories.
- **Output**: A published Artifact dashboard, grouped by category, updated in
  place daily (stable URL) — plus a brief daily push notification.
- **Schedule**: Daily, 7:00 AM Singapore time (UTC+8).
- **Persistence**: A JSON store to dedupe across days and retain history,
  since each scheduled run starts with no memory except what's on disk.

An existing scheduled routine on this machine,
`C:\Users\USER\.claude\scheduled-tasks\lorong-ai-weekly-events\SKILL.md`, is
the concrete template for how the `schedule` skill structures a routine (YAML
frontmatter + `## Objective/Steps/Output Format/Push Notification/Constraints`,
ending in a `PushNotification` call) and confirms the available tools
(`WebSearch`, `WebFetch`, `PushNotification`). Follow that convention rather
than inventing a new structure.

## Architecture

**Two locations, two purposes:**

1. **`C:\Users\USER\.claude\scheduled-tasks\construction-news-agent\SKILL.md`**
   — the routine's full instructions (created/edited via the `schedule`
   skill), inlined in the same style as `lorong-ai-weekly-events\SKILL.md`.
   This is the "program" that runs daily.
2. **`C:\Users\USER\0. Claude Projects\Construction News Agent\`** (this
   folder) — the project's data and output, since these are user-facing
   artifacts, not internal routine plumbing:
   - `news_store.json` — persistent article store (dedup + history)
   - `dashboard.html` — Artifact source file, regenerated and republished in
     place each run
   - `backups/news_store_<YYYYMMDD_HHMMSS>.json` — timestamped pre-write
     backups
   - `README.md` — human-facing doc: what this is, the schedule, category
     list, how to adjust sources

If, when actually setting up the routine via the `schedule` skill, the
execution environment cannot reliably read/write this local project path,
fall back to keeping `news_store.json`/`dashboard.html` alongside `SKILL.md`
under the scheduled-tasks folder instead (guaranteed accessible, per the
existing example). Verify this at setup time — it does not change anything
else in the design.

## Data schema — `news_store.json`

```json
{
  "schema_version": 1,
  "last_run": "2026-08-18T07:00:00+08:00",
  "articles": [
    {
      "url": "https://www.straitstimes.com/singapore/...",
      "title": "BCA awards $200m tender for Tuas mega hospital",
      "source": "The Straits Times",
      "category": "Project Awards/Tenders",
      "summary": "BCA has awarded a $200m construction tender for a new hospital in Tuas, with completion slated for 2029.",
      "date_published": "2026-08-17",
      "date_found": "2026-08-18",
      "is_new_today": true
    }
  ]
}
```

- `url` is the dedup key, normalized (strip tracking params/fragment/trailing
  slash, lowercase scheme+host) before comparing.
- `is_new_today` is recomputed every run (`date_found == today`), not a
  sticky flag — it drives the dashboard's "NEW" badge.
- `date_published` falls back to `date_found` if genuinely unavailable.

## The 9 fixed categories (with priority order for ambiguous articles)

1. **Accidents/Workplace Safety** — any injury/death/safety incident always
   wins, even if it also touches policy or a named company.
2. **Legal & Disputes/Arbitration** — active lawsuits, arbitration, contract
   disputes.
3. **Policy/Regulatory** — new laws, BCA/MOM/URA/HDB regulatory changes,
   codes of practice, licensing.
4. **Project Awards/Tenders** — tender wins, contract awards,
   groundbreakings/completions as project milestones.
5. **Sustainability/Green Building** — Green Mark, carbon/net-zero,
   sustainable materials, when that IS the story.
6. **Manpower/Labour** — workforce policy, foreign worker quotas, training,
   labour shortages (distinct from a specific safety incident).
7. **New Technology/Innovation** — BIM, robotics, prefab/DfMA, AI in
   construction, when the innovation is the story.
8. **Public Feedback/Community** — resident objections, public consultations,
   community impact.
9. **Media Features/Company News** — default bucket: profiles, executive
   moves, PR, earnings, awards/rankings not covered above.

Off-topic results (not Singapore, not construction/built-environment) are
discarded, not force-fit into a category.

## Daily routine logic (becomes the body of `SKILL.md`)

**Step 0 — Load state**: Read `news_store.json`; if missing/invalid, treat as
first run with an empty store. Build a normalized `known_urls` set. Note
today's date in SGT.

**Step 1 — Gather candidates**: Run WebSearch queries per source/category
seed (e.g. `site:straitstimes.com construction Singapore`,
`site:businesstimes.com.sg construction OR "built environment" Singapore`,
BCA/HDB/URA press releases, `site:constructionplusasia.com Singapore`, plus
category-seeded queries for safety, sustainability, manpower, disputes).
Window: last 24–48h on normal runs; last 7 days on first run. Don't abort the
run if one source is unreachable/paywalled — skip it and continue.

**Step 2 — Filter**: Discard off-topic results. Normalize URLs and drop
anything already in `known_urls`. For survivors, use WebFetch (or a
sufficient search snippet) to confirm title/date/content.

**Step 3 — Classify & summarize**: One category per article via the priority
rubric above; factual 1–2 sentence summary, no editorializing.

**Step 4 — Update store**: Append new entries (`date_found` = today,
`is_new_today` = true); set `is_new_today` = false on all others; drop
entries with `date_found` older than 90 days; back up the current file to
`backups/` before overwriting; write updated store with new `last_run`.

**Step 5 — Regenerate dashboard**: Rebuild `dashboard.html` from the *full*
retained store, grouped by the 9 categories, newest-first by
`date_published` within each, "NEW" badges, per-category + total counts.
Consult the `artifact-design` skill for styling/theme/responsive/favicon
conventions before finalizing markup. Publish via the Artifact tool using
the **same `file_path`** every run so the URL stays stable.

**Step 6 — Notify**: Always send one `PushNotification` (<200 chars, one
line, no markdown), e.g. `"Construction News: 5 new (2 Tenders, 1 Safety, 1
Sustainability). Dashboard: <url>"`, or `"...no new SG construction stories
today. Dashboard unchanged: <url>"` on a quiet day, or a failure message if
the run couldn't complete.

**First-run behavior**: Widen to a 7-day window, build the initial
dashboard, and send a "set up complete" style notification instead of an
alarming article count.

**Error handling**: Continue past individual source failures. On total
failure (no sources reachable), skip writing the store/dashboard (don't
overwrite good data with nothing) and send a failure notification instead.
If `news_store.json` is corrupt, restore from the latest `backups/` file
rather than silently resetting; notify and stop if still unreadable.

## Setup steps (implementation phase — not yet done)

1. Create `README.md` in this folder.
2. Create `news_store.json` seed
   (`{"schema_version":1,"last_run":null,"articles":[]}`).
3. Write `dashboard.html` (initial empty-state version, per `artifact-design`
   skill guidance) and publish it once via the Artifact tool to establish
   the stable URL.
4. Use the **`schedule` skill** to create the recurring routine — name it
   `construction-news-agent`, daily at 7:00 AM Singapore time (confirm during
   the skill's own setup flow whether it wants local time or UTC — if UTC,
   that's 23:00 UTC the previous day), with the full instructions from this
   file's "Daily routine logic" section as the `SKILL.md` body (following the
   `lorong-ai-weekly-events` template structure: Objective/Steps/Output
   Format/Push Notification/Constraints).
5. Trigger one manual run of the routine to validate end-to-end before
   relying on the schedule.

## Verification

- After the first manual run: confirm `news_store.json` contains plausible
  articles with correct categories/URLs/dates, `backups/` has a snapshot,
  and `dashboard.html` was republished (open the Artifact URL and check it
  renders, is grouped correctly, shows "NEW" badges, and is stable across a
  second run — same URL, no duplicate articles).
- Confirm a `PushNotification` was received with an accurate, concise
  summary.
- Confirm the routine is listed and scheduled correctly (list scheduled
  routines via the `schedule`/cron tooling) for 7:00 AM SGT daily.
- Spot-check dedup by re-running immediately after a successful run: it
  should find ~0 new articles and say so, not re-add duplicates.

## Open risks / assumptions (flagged, not blocking)

- Cloud vs. local execution filesystem access for the routine — verify at
  `schedule` skill setup time; fallback path noted above if needed.
- Straits Times/Business Times are paywalled for full text; search snippets
  + WebFetch of ledes should suffice for classification/summaries — revisit
  if insufficient.
- `WebSearch`'s tool description mentions US-oriented results;
  `allowed_domains` per-source filtering should mitigate bias for
  SG-specific sources.
- No RSS-specific tool exists in this environment; RSS/press-release pages
  are fetched via `WebFetch` as a fallback, not true RSS parsing.
- 90-day retention and 7-day first-run window are sensible defaults,
  adjustable later if the user wants a different history depth.
