# Construction News Agent (Singapore) — Daily Scheduled Digest

> Status: **Live.** Built and running as of 2026-09-06. This file remains the
> design reference the daily routine reads each run — treat the rest of this
> document as historical intent, and the notes below as what actually shipped
> and has changed since.

## Post-launch amendments

- **Branch-per-run drift discovered and fixed (2026-09-11)**: starting around
  2026-09-09, the environment launching each scheduled run began assigning a
  fresh, randomly-named feature branch per session and blocking pushes to
  `main` without explicit permission — a Claude Code GitHub-session
  convention imposed from outside this routine, not something this routine's
  prompt controls (it still says `git push origin main`, per Step 6 below).
  Effect: the scheduled trigger fired **twice** on 2026-09-09, producing two
  divergent branches (`claude/keen-bardeen-bgkmi5`,
  `claude/keen-bardeen-fyz0mx`) that each committed their day's findings but
  never reached `main`; the next day's run forked from the stale pre-9/9
  `main`, unaware of either, and had to forensically recover both branches'
  articles from GitHub by hand to avoid regressing the published dashboard.
  `main` was three days stale before this was caught and fast-forwarded back
  in line; the two orphaned branches were left in place (their data is fully
  contained in `main`) since branch *deletion* hit a separate permissions
  wall — the session's git credential allows creating/updating branches but
  returns 403 on deleting a ref, and the GitHub MCP tools available don't
  expose branch deletion either.
  **Mitigation applied**: Step 6 below now ends every run by fast-forwarding
  `main` to whatever branch the run was forced onto (`git push origin
  <branch>:main`, safe precisely because that branch is always a fast-forward
  descendant of `main` — it forked from `main` and only adds commits), so a
  branch-per-run environment can no longer let unmerged work accumulate: each
  run closes the loop itself instead of leaving an orphan for the next run to
  discover. This does not fix the root cause (still worth checking whether
  the schedule/trigger config can be set to a plain non-GitHub-session
  execution mode, or at least to fire only once daily), only prevents it from
  compounding. If a future run finds `git push origin <branch>:main` refused
  (e.g. `main` has since diverged with commits `<branch>` doesn't contain),
  stop and flag it rather than forcing — that would mean something else
  wrote to `main` out-of-band and needs a real merge, not a fast-forward.

- **Execution model differs from the original plan below**: instead of a
  local `.claude\scheduled-tasks\` routine, this runs as a **cloud routine**
  (`construction-news-agent`, created via the `schedule` skill's RemoteTrigger
  flow) on a public GitHub repo,
  [Keanlim86/construction-news-agent](https://github.com/Keanlim86/construction-news-agent).
  Each scheduled fire clones that repo fresh, does the day's work, commits the
  result back, and publishes the dashboard — there is no local persistence on
  this PC and no `SKILL.md` file; the routine's full instructions live as the
  routine's own prompt (edit via the `schedule` skill or claude.ai/code/routines).
- **`news_archive.json` added (2026-09-06)**: a permanent, append-only record
  of every article that ages out of `news_store.json`'s 90-day window,
  instead of those articles being dropped outright. See the updated Step 4
  below and [README.md](README.md#history--retention) for the schema and
  rationale.
- **Company watchlist added (2026-09-06)**: category 9 (Media Features/
  Company News) was going empty most days — the search queries are
  source-based and category-seeded, not company-name-based, so routine items
  like an earnings report (e.g. Wee Hur's 1HFY2026 results) weren't
  surfacing. Step 1 now also runs one search pass per watchlisted company.
  Watchlist (SGX-listed contractors/developers with active construction
  arms): **Wee Hur, BRC Asia, Lian Beng, Koh Brothers, Hock Lian Seng, CSC
  Holdings, Chip Eng Seng, UOL Group, CapitaLand, City Developments, Tiong
  Seng, BBR, Hwa Seng**. To add/remove a company, edit this list and the
  routine's prompt (Step 1) to match — see
  [README.md](README.md#adjusting-sources).
- **Data centre queries added to Step 1 (2026-09-08)**: the 2026-09-08 run
  included an ad hoc addition — a CNA story on Bangkok data centres facing
  safety/regulatory scrutiny (category 10, International/Regional News: a
  regional construction-regulatory shift, no direct SG link) — after the
  user pointed out that data centre construction, safety and
  community-reaction stories are a coverage gap, both internationally and
  **locally in Singapore** (e.g. Keppel DC Singapore 9, the JTC/NUS Jurong
  Island low-carbon data centre park, DayOne's hydrogen-powered facility, and
  any future site-level safety incidents or resident objections near one).
  Step 1 now also runs a dedicated data-centre query pair: `data centre
  Singapore construction OR safety OR tender OR community` (Singapore angle —
  routes to whichever of categories 1/4/7/8/9 fits the story) and `data
  centre Asia safety OR regulatory OR community reaction` (category 10 angle,
  alongside the existing Bloomberg pass), with the same wider 7–14 day window
  as the company watchlist since these stories are lower-frequency. Applied
  directly to the routine's prompt by the user via the `schedule` skill /
  claude.ai/code/routines (this session has no tool that reaches the
  persistent routine config directly).
- **Changi Airport Group newsroom added as a source (2026-09-08)**:
  backfilled one article the existing queries had missed — CAG's 16 July
  2026 release announcing a contract award to Nakano Singapore for a new
  six-storey office development at Terminal 3 (Project Awards/Tenders).
  CAG's newsroom (changiairport.com/en/corporate/our-media-hub/newsroom.html)
  is a major Singapore construction/infrastructure source in its own right
  (Terminal 5, landside developments, contract awards) that Step 1's source
  list didn't cover. Step 1 now also names Changi Airport Group's newsroom
  directly among the Singapore construction sources (alongside the
  BCA/HDB/URA newsroom passes), with the same wider 7–14 day window as the
  company watchlist and data-centre queries, since a plain `site:` search
  didn't index the newsroom's article content well — worth leaning on
  aviation/construction trade press (e.g. Passenger Terminal Today, Future
  Travel Experience) as a cross-check when CAG's own page comes back thin.
  Applied directly to the routine's prompt by the user via the `schedule`
  skill / claude.ai/code/routines (this session has no tool that reaches the
  persistent routine config directly).

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
- **Scope**: Singapore-focused construction industry news, plus a dedicated
  bucket for major international/regional construction-industry news (see
  category 10 below) even without a direct Singapore angle.
- **Sourcing**: Web search + RSS/press-release pages across a default set of
  SG sources (Straits Times, Business Times, CNA, BCA newsroom, HDB/URA press
  releases, Construction Plus Asia, and similar), refined over time — not
  fixed per-site HTML scrapers. Also searches **Bloomberg** (`site:bloomberg.com`)
  for major international/regional construction, property and real-estate
  finance stories (e.g. a large developer's insolvency, a private-credit
  fund's exposure) to feed category 10.
- **Categorization**: The scheduled Claude agent itself reads and classifies
  each article (no separate classifier/API) into 10 fixed categories.
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

## Data schema — `news_archive.json` (added 2026-09-06)

```json
{
  "schema_version": 1,
  "articles": [
    {
      "url": "https://www.straitstimes.com/singapore/...",
      "title": "BCA awards $200m tender for Tuas mega hospital",
      "source": "The Straits Times",
      "category": "Project Awards/Tenders",
      "summary": "BCA has awarded a $200m construction tender for a new hospital in Tuas, with completion slated for 2029.",
      "date_published": "2026-08-17",
      "date_found": "2026-08-18",
      "archived_on": "2026-11-16"
    }
  ]
}
```

Same article shape as `news_store.json` minus `is_new_today` (meaningless
once archived) plus `archived_on` (the date it was moved here, i.e. when it
crossed the 90-day threshold in the active store). Append-only — nothing
ever removes an entry from this file, and nothing reads it back into
`news_store.json` automatically. It does not feed the dashboard; it exists
purely as a durable history for anyone who wants to look further back than
90 days.

## The 10 fixed categories (with priority order for ambiguous articles)

Categories 1–9 are for **Singapore** construction/built-environment news.
Category 10 is a separate catch-all for major **international/regional**
construction-industry news that has no direct Singapore angle — it sits
outside the 1–9 priority order (which exists only to resolve ambiguity
*within* Singapore-relevant stories) and is only reached once an article has
already failed the Singapore test.

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
   community impact; also environmental/green-space clearing backlash (e.g.
   public uproar or nature-group petitions over clearing a forest/green site
   such as Clementi/Maju Forest for a development) — distinct from category 5
   (Sustainability/Green Building), which is for a building's own green
   credentials, not objections to clearing land for one.
9. **Media Features/Company News** — default bucket: profiles, executive
   moves, PR, earnings, awards/rankings not covered above.
10. **International/Regional News** — major global/regional construction,
    property-development or real-estate-finance stories with no direct
    Singapore link but clear relevance to the industry (a large developer's
    insolvency, a private-credit fund's exposure, a major cross-border
    infrastructure award, a regional regulatory shift). Sourced mainly via
    Bloomberg; keep the bar high — this is not a catch-all for every
    non-Singapore construction story, only ones a Singapore industry reader
    would want to know about.

Results that are neither Singapore-relevant (1–9) nor a major
international/regional story clearing category 10's bar are discarded, not
force-fit into a category.

## Daily routine logic (becomes the body of `SKILL.md`)

**Step 0 — Load state**: Read `news_store.json`; if missing/invalid, treat as
first run with an empty store. Build a normalized `known_urls` set. Note
today's date in SGT.

**Step 1 — Gather candidates**: Run WebSearch queries per source/category
seed (e.g. `site:straitstimes.com construction Singapore`,
`site:businesstimes.com.sg construction OR "built environment" Singapore`,
BCA/HDB/URA press releases, `site:constructionplusasia.com Singapore`, plus
category-seeded queries for safety, sustainability, manpower, disputes).
Also run a `site:bloomberg.com` pass for major international/regional
construction, property-development or real-estate-finance stories (category
10 candidates) — e.g. `site:bloomberg.com construction OR property developer
insolvency Asia`. Window: last 24–48h on normal runs; last 7 days on first
run. Don't abort the run if one source is unreachable/paywalled — skip it
and continue.

**Step 2 — Filter**: Discard results that are neither Singapore-relevant nor
a major international/regional story clearing category 10's bar. Normalize
URLs and drop anything already in `known_urls`. For survivors, use WebFetch
(or a sufficient search snippet) to confirm title/date/content — Bloomberg is
often paywalled, so a clear, specific search snippet plus a cross-check
against one freely-accessible outlet reporting the same facts is sufficient
if the article itself 403s.

**Step 3 — Classify & summarize**: One category per article — categories 1–9
via the priority rubric above for Singapore-relevant stories, else category
10 if it clears that category's bar; factual 1–2 sentence summary, no
editorializing.

**Step 4 — Update store**: Append new entries (`date_found` = today,
`is_new_today` = true); set `is_new_today` = false on all others; for any
entry with `date_found` older than 90 days, append it to
`news_archive.json` (adding an `archived_on` = today field; create the file
with `{"schema_version": 1, "articles": []}` if missing) and then drop it
from the active store — never delete an article without archiving it first;
back up the current `news_store.json` to `backups/` before overwriting;
write updated store with new `last_run`.

**Step 5 — Regenerate dashboard**: Rebuild `dashboard.html` from the *full*
retained store, grouped by the 10 categories, newest-first by
`date_published` within each, "NEW" badges, per-category + total counts.
Consult the `artifact-design` skill for styling/theme/responsive/favicon
conventions before finalizing markup. Publish via the Artifact tool using
the **same `file_path`** every run so the URL stays stable.

**Step 6 — Commit, push, land on `main`, and notify**: Commit the changed
files and push. If the execution environment assigned this run its own
branch rather than letting it commit straight to `main` (see the
branch-per-run amendment above — check `git branch --show-current`; if it's
`main`, this sub-step is a no-op), immediately fast-forward `main` to that
branch's tip: `git push origin <branch>:main`. This is always a safe
fast-forward, never a merge or a force-push, because the run's branch forked
from `main` and only ever adds commits on top of it — if that push is
refused (non-fast-forward), stop and flag it rather than forcing; that means
something else committed to `main` out-of-band since this run started and
needs an actual merge. Skipping this step is how `main` silently goes stale
while unmerged branches pile up (see the amendment above for what that cost
on 2026-09-09 to 2026-09-11) — treat it as mandatory, not cleanup. Then
always send one `PushNotification` (<200 chars, one line, no markdown), e.g.
`"Construction News: 5 new (2 Tenders, 1 Safety, 1 Sustainability).
Dashboard: <url>"`, or `"...no new SG construction stories today. Dashboard
unchanged: <url>"` on a quiet day, or a failure message if the run couldn't
complete.

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
