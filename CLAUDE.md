# Construction News Agent (Singapore) — Daily Scheduled Digest

> Status: **Live since 2026-09-06.** This file is the design reference the
> daily routine reads each run. As of 2026-09-30 it matches the routine's
> live prompt; when either changes, update the other (see Routine management).

## How it runs

- **Cloud routine** `construction-news-agent` (created via the `schedule`
  skill), daily **07:00 SGT (23:00 UTC prev. day)**, on public repo
  [Keanlim86/construction-news-agent](https://github.com/Keanlim86/construction-news-agent).
  Each fire clones the repo fresh, works, commits back, publishes the
  dashboard. No local persistence, no `SKILL.md`: the routine's instructions
  live in its own prompt (edit via the `schedule` skill or
  claude.ai/code/routines).
- **Routine config is reachable from a cloud session** via the
  Claude_Code_Remote tools: `list_triggers`/`get_trigger` read the live
  prompt, `update_trigger` replaces it (whole prompt, never a diff — a partial
  paste once dropped the rest of it, 2026-09-21). Trigger id
  `trig_01XiwXHr6pxUX42vwhZZ3Qm4`, model `claude-sonnet-5`, cron `0 23 * * *`
  UTC. (`CronCreate`/`CronList` are an unrelated session-only scheduler.)
  Earlier notes saying no session could reach the config are obsolete.
- **Repo files**: `news_store.json` (active store, 90 days, drives the
  dashboard), `news_archive.json` (append-only history), `dashboard.html`,
  `archive.html`, `backups/news_store_<YYYYMMDD_HHMMSS>.json`, `README.md`
  (human doc), `Link.txt` (dashboard URL), `usage_log.csv` (per-run token
  usage, written by the tracker routine — the news routine never touches it).
- **Published pages**:
  - Dashboard: https://claude.ai/code/artifact/092b0df4-41bf-4f2f-9b53-6983fe8902d1
    (`.../artifact/28fUQ9iv...` is a short alias of the same artifact, not a
    duplicate). Sharing: "Anyone with the link".
  - Archive: [Blueprint Brief Archive](https://claude.ai/artifact/5wVjEVJvDELacJ3DH1NUt5).
    **Manual to-do**: created private by default — the user must change its
    sharing via the page's Share menu or the dashboard's Archive button
    won't work for others.
- **Repo file is source of truth** if `dashboard.html` in the repo and the
  live artifact disagree. If someone publishes to the artifact directly
  (out of band), read the live HTML and sync it into the repo verbatim —
  this silently diverged once (2026-09-21 controls-bar).

## The 10 categories (priority order resolves ambiguity within 1–9)

Categories 1–9 are Singapore construction/built-environment news. Category
10 sits outside that order and is only reached after an article fails the
Singapore test.

1. **Accidents/Workplace Safety** — any injury/death/safety incident always wins.
2. **Legal & Disputes/Arbitration** — lawsuits, arbitration, contract disputes.
3. **Policy/Regulatory** — new laws, BCA/MOM/URA/HDB rules, codes of practice, licensing.
4. **Project Awards/Tenders** — tender wins, contract awards, groundbreakings/completions as milestones.
5. **Sustainability/Green Building** — Green Mark, carbon/net-zero, sustainable materials, when that IS the story.
6. **Manpower/Labour** — workforce policy, worker quotas, training, shortages, worker housing supply (not a specific incident).
7. **New Technology/Innovation** — BIM, robotics, prefab/DfMA, AI, worksite tech trials, when the innovation is the story.
8. **Public Feedback/Community** — resident objections, consultations, community impact; also backlash over clearing forest/green sites (distinct from 5, which is a building's own green credentials).
9. **Media Features/Company News** — default: profiles, exec moves, PR, earnings, awards/rankings.
10. **International/Regional News** — major global/regional construction, property-development or real-estate-finance stories with no direct SG link (developer insolvency, private-credit exposure, major cross-border award, regional regulatory shift). Mainly via Bloomberg; high bar, not a catch-all.

Anything neither SG-relevant nor clearing category 10's bar is discarded, not force-fit.

## Data schemas

`news_store.json`:
```json
{
  "schema_version": 1,
  "last_run": "2026-08-18T07:00:00+08:00",
  "articles": [{
    "url": "https://www.straitstimes.com/singapore/...",
    "title": "BCA awards $200m tender for Tuas mega hospital",
    "source": "The Straits Times",
    "category": "Project Awards/Tenders",
    "summary": "BCA has awarded a $200m construction tender for a new hospital in Tuas, with completion slated for 2029.",
    "date_published": "2026-08-17",
    "date_found": "2026-08-18",
    "is_new_today": true
  }]
}
```
- `url` is the dedup key, normalized (strip tracking params/fragment/trailing
  slash, lowercase scheme+host). Dedup is **strictly URL-based**: one outlet's
  URL may represent an event (by design), but a *different* URL for the same
  event — especially a primary source adding new facts — is not a duplicate.
- `is_new_today` is recomputed every run (`date_found == today`); drives NEW badges.
- `date_published` falls back to `date_found` only if genuinely unavailable.

`news_archive.json` (append-only; created as `{"schema_version": 1, "articles": []}`
if missing): same article shape minus `is_new_today`, plus `archived_on`
(date it crossed 90 days). Nothing removes entries or reads them back into
the store; it feeds only `archive.html`.

## Daily routine logic

**Step 0 — Load state**: read `news_store.json` (if corrupt, restore from the
latest `backups/` file; if still unreadable, notify and stop; if missing,
treat as first run). Build normalized `known_urls`. Note today's SGT date.

**Step 1 — Gather candidates**. Window: last 24–48h normally; 7 days on first
run. "Wide window" below = 7–14 days on any run (lower-frequency sources).
Skip any unreachable/paywalled source and continue.

- **Source searches (WebSearch)**: `site:straitstimes.com`, `site:businesstimes.com.sg`,
  CNA construction/property, BCA/HDB/URA press releases,
  `site:constructionplusasia.com`.
- **Changi Airport Group newsroom (wide)**:
  changiairport.com/en/corporate/our-media-hub/newsroom.html — `site:` search
  indexes it poorly; cross-check with trade press (Passenger Terminal Today,
  Future Travel Experience).
- **MND speeches + press releases (wide, `curl`)**: mnd.gov.sg is a
  client-rendered Next.js app WebFetch/WebSearch can't read, so call its
  Directus API. Listing:
  `curl -sG "https://www.mnd.gov.sg/api/articles" --data-urlencode "filter[and][0][status][eq]=published" --data-urlencode "filter[and][1][article_type][eq]=<TYPE>" --data-urlencode "sort=-article_date_time" --data-urlencode "limit=15" --data-urlencode "fields=title,url,article_date_time"`
  with `<TYPE>` = `e45b3aaf-3de0-4c98-922a-d5ad73ab5c0b` (speeches) or
  `bcb1e98c-5a6c-4f76-a93a-6c263b9aecda` (press releases). Full text: same
  call with `filter[and][1][url][eq]=<slug>` and `fields=*,title.*`; HTML is in
  `content`. Press releases are mainly a redundancy check (WebSearch often
  fails to surface stories mainstream outlets did cover). **Always fetch full
  text for relevant titles even if a same-event story from another outlet is
  already stored** — `known_urls` rules out exact URLs, never topics; add the
  MND URL as its own entry if it adds material specifics, else skip. The
  `curl` approach is MND-specific; don't generalise it without the same
  JS-rendering problem.
- **Straits Times (wide, `curl`)**: `curl -sS "https://www.straitstimes.com/news/singapore/rss.xml"`
  (parse `<item>` `<title>`/`<link>`/`<pubDate>`; trust `<pubDate>`) and
  `curl -sS "https://www.straitstimes.com/tags/ministry-of-national-development?ref=see-more-on"`
  (raw HTML; extract titles/URLs — MND housing/land stories lacking a
  "construction" keyword).
- **Business Times (wide, `curl`)**: `curl -sS "https://www.businesstimes.com.sg/rss.xml"`,
  parsed like ST's feed. Site-wide feed; most items are discarded.
- **LTA newsroom (wide, `curl`)**:
  `curl -sS https://www.lta.gov.sg/content/ltagov/en/newsroom.html` — one
  ~1.1MB static page with every News Release/Media Reply since 2020 (filters
  are client-side; no params needed). Parse each `<li class="item">`:
  `<h5 class="mt-3 title"><a href>` title/URL, `<p class="news-paragraph">`
  summary, `<span class="date" style="display:none;">YYYY-MM-DD</span>` date
  (trust it). Keep contract awards, tunnelling/viaduct progress, MRT/road
  milestones, worksite safety/community items; discard fare/ERP/COE/bus/
  licensing notices. WebFetch each kept press-release page for full text
  (reliable per article; **not** on the listing page — its summarizer sampled
  Jan 2020 entries). If unreachable, fall back to WebSearch
  `site:lta.gov.sg newsroom "awards" OR contract OR tender OR construction` and
  `Singapore LTA contract awarded OR tender OR viaduct OR MRT line construction OR tunnelling`
  plus a cross-check — but try `curl` first every run (reachability varies by
  environment: one session got proxy 403, another 200; if blocked, add
  `www.lta.gov.sg` to the environment's allowed domains).
- **Category seeds**: safety, sustainability, manpower, disputes, tenders, plus
  dedicated queries:
  - Tech: `Singapore construction robots OR robotics OR automation OR autonomous machinery OR BIM`
  - Policy: `Singapore URA OR BCA OR HDB OR MOM construction OR building policy OR guideline OR regulation review`
    (guideline reviews, e.g. URA GFA rules, often lack "construction").
  - Materials: `Singapore construction sand OR cement OR concrete OR steel OR rebar supply OR shortage OR price`
    (import ban → cat. 3; company operations → cat. 9; unless 1/2/4 applies).
  - Heat stress: `Singapore construction heat stress OR outdoor worker cooling OR heat-resilient wearable OR climate adaptation worksite`
    (MOM's mandatory heat stress framework starts Dec 2026). Won't catch a
    single buried mention in an unrelated headline — accepted tradeoff.
- **Bloomberg (cat. 10)**: e.g. `site:bloomberg.com construction OR property developer insolvency Asia`.
- **Data centres (wide)**: `data centre Singapore construction OR safety OR tender OR community`
  (routes to 1/4/7/8/9) and `data centre Asia safety OR regulatory OR community reaction` (cat. 10).
- **Purpose-built dormitories (wide)**:
  `Singapore purpose-built dormitory OR "worker dormitory" tender OR site OR construction`
  → usually cat. 6; an awarded/closed land tender → cat. 4.
- **Semiconductor/pharma/high-tech plants (wide)**:
  `Singapore semiconductor fab OR wafer fab OR chip plant OR pharmaceutical plant OR biomanufacturing facility groundbreaking OR opening OR construction`
  — often reported as tech/business news on GlobeNewswire/SEMI/EDB.
- **Company/entity watchlist (wide)** — one query per name ("named
  companies/agencies worth a per-name pass", not strictly SGX-listed):
  Wee Hur, BRC Asia, Lian Beng, Koh Brothers, Hock Lian Seng, CSC Holdings,
  Chip Eng Seng, UOL Group, CapitaLand, City Developments, Tiong Seng, BBR,
  Hwa Seng, Kajima, JTC, Kok Tong Construction, KTC Engineering, The GEAR by
  Kajima, Pan-United Corporation, Continental Steel.
  - Kok Tong Construction Pte Ltd and **KTC Civil Engineering & Construction
    Pte Ltd** are separate sister companies (KTC Group, 27 Pandan Crescent) —
    separate queries, attribute hits to the correct one.
  - The GEAR by Kajima (Global Engineering, Architecture & Real Estate;
    Changi Business Park, opened 16 Aug 2023) is Kajima's Asia HQ and
    tech co-creation hub (houses KaTRIS) — not a separate company, but
    coverage often names only "The GEAR".
  - Pan-United (SGX: P52): SG's largest ready-mix concrete producer (~40%
    share), only carbon-mineralised concrete provider. Continental Steel:
    major SEA steel supplier (SG rebar/steel fibre).
  - Keep this list in sync with README.md and the routine prompt.

**Step 2 — Filter**: discard non-SG stories that don't clear cat. 10's bar;
normalize URLs; drop anything in `known_urls`. Confirm survivors via WebFetch
(or `curl` where WebFetch is blocked). Paywall fallback: a clear, specific
search snippet plus a cross-check against one freely-accessible outlet with
the same facts. Verify dates — WebSearch can resurface old stories as
"recent" (see Source quirks).

**Step 3 — Classify & summarize**: one category per article via the rubric;
factual 1–2 sentence summary, no editorializing.

**Step 4 — Update store**: append new entries (`date_found` = today,
`is_new_today` = true); set all others false; move any entry with
`date_found` > 90 days old into `news_archive.json` with `archived_on` = today
(never delete without archiving); back up `news_store.json` to `backups/`;
write the store with new `last_run`.

**Step 5 — Regenerate & publish**: rebuild `dashboard.html` from the full
store, grouped by the 10 categories, newest `date_published` first within
each, NEW badges, per-category and total counts. Follow `artifact-design`
conventions (Blueprint Brief tokens: Fraunces / IBM Plex Sans / IBM Plex Mono,
blueprint-grid background). Publish: Artifact `read` the stable dashboard
URL, then `publish` `dashboard.html` with `url` set to it (same title "Blueprint
Brief", omit the icon) so it updates in place.
**Preserve this template chrome exactly — never drop, simplify, or re-derive it:**
- **Search bar** + `applyFilter()`: a card must match the keyword query, the
  today-only state, *and* the selected date.
- **`.controls-bar`**: `#todayToggle` pill (shows only `is-new` cards);
  `#datePicker`/`#dateSelect` dropdown populated from cards' `.date` text,
  newest first, formatted `DD/MM/YY`; an **Archive** `.ctrl-btn` (filing-box
  icon, `target="_blank"`) linking to the archive page URL above.
- **Collapse**: `buildCollapse()` IIFE per `.cards` block moves `is-new`
  cards to the top (relative order kept) and caps visible cards at
  `VISIBLE_TOTAL = 2` (visible old = `max(0, 2 - newCount)`); remaining old
  cards go in a hidden `.cards-extra` revealed by a `.more-toggle` ("Show N
  more" + rotating chevron, right-aligned via `justify-content:flex-end`,
  `2px dashed var(--green)` top border, no other button chrome).
  `syncCollapse(filtersActive)` force-expands a group while any filter is
  active and restores its prior state when cleared.
- Generated markup must keep: one `.cards` container per category of sibling
  `article.card` elements, `is-new` on today's finds.
- **`archive.html` is never regenerated.** It fetches `news_archive.json`
  client-side via a relative URL (the artifact CSP blocks external hosts,
  incl. GitHub raw) and renders legend, stats, search, `.archived` pills
  (showing `archived_on`), empty and load-error states from it; no NEW badges
  or collapse. Only on runs where Step 4 archived something: Artifact
  `publish` with `url` = the archive page URL and
  `files: {"news_archive.json": "news_archive.json"}`, no `file_path`.

**Step 6 — Commit, push, land on `main`, notify**: commit and push. The
environment may force a per-run branch and block direct pushes to `main`;
check `git branch --show-current` and, if not `main`, fast-forward it:
`git push origin <branch>:main` (safe — the branch forked from `main` and only
adds commits). If refused as non-fast-forward, **stop and flag it**, never
force (something wrote to `main` out of band). This is mandatory: skipping
it left `main` 3 days stale and two orphan branches in 2026-09-09..11 (the
trigger also fired twice on 09-09). The session git credential can't delete
refs (403), so orphan branches can't be cleaned up from a session. Then send
one `PushNotification` (<200 chars, one line, no markdown), e.g.
`Construction News: 5 new (2 Tenders, 1 Safety, 1 Sustainability). Dashboard: <url>`,
or a quiet-day, first-run, total-failure, or "main has diverged — needs
manual merge" message. On total failure, write and push nothing.

**First run**: 7-day window, build initial dashboard, "set up complete"
notification. **Total failure** (no sources reachable): don't write the
store/dashboard; send a failure notification.

## Usage tracking

Routine `construction-news-usage-tracker` (`trig_01Lh6Rj6Krt4jvvBfqiZgC2j`,
Haiku, daily 08:28 SGT, fresh session per fire) reads the news routine's
`last_run` session usage via `list_triggers` + `get_session`, and appends one
row to `usage_log.csv` (date, session, model, status, minutes, input/output/
cache-read/cache-write tokens, cost_usd), committed straight to `main`. It
runs separately because the news routine has no Claude_Code_Remote connector
and can't read its own usage. Only the *latest* run is queryable, so a missed
day can't be backfilled. `cost_usd` is the session's API-price estimate, and
it includes any chat someone adds to the run session afterwards. Baseline
(2026-09-30 run): ~630k input+output, 32.7M cache-read tokens, ~US$11.34;
cache reads dominate, driven by the number of tool calls per run.
**Setup status**: the tracker needs the Claude_Code_Remote connector (for
`list_triggers`, `get_session`, `add_repo`). Routines created from a session
store no connectors, and its first test run (2026-09-30) had none and logged
nothing. Add the connector to the routine at claude.ai/code/routines. Until
then it no-ops daily (~US$0.07/run).

## Source quirks (learned the hard way)

- **straitstimes.com**: WebFetch refuses the whole domain; `curl` works (200).
  Pre-2026-09-21 ST entries were built from snippets + cross-checks, not direct fetches.
- **WebSearch misdating**: snippets can present old stories as current (a PIE
  and an Upper Changi story turned out to be Sept 2023 / Sept 2025). Prefer
  publisher timestamps (RSS `<pubDate>`, LTA hidden date span, MND API dates).
- **Large listing pages** (LTA, ST tag page, RSS): fetch raw with `curl` and
  parse locally; WebFetch's summarizer is unreliable on them. WebFetch is fine
  on individual LTA press-release pages.
- **JS-rendered sites** (MND): use the underlying API, not the page.
- **Title-driven triage** misses construction detail buried in unrelated
  headlines; accepted tradeoff.
- **Live prompt check**: the MND full-text call should read
  `fields=*,title.*`; the trigger listing on 2026-09-30 showed `fields=,title.`
  (possibly just display stripping). Verify with `get_trigger` if MND full text
  comes back empty.

## Backfill log (misses found by the user, fixed in store + dashboard)

| Date | Story | Cat. | Gap |
|---|---|---|---|
| 09-08 | CAG contract to Nakano Singapore, T3 six-storey office (16 Jul 2026) | 4 | CAG newsroom not a source (now added) |
| 09-08 | CNA: Bangkok data centres under safety/regulatory scrutiny | 10 | No data-centre query (now added) |
| 09-12 | [JTC PBD sites Mandai ~15,000 / Upper Jurong ~8,100 beds, tender H2 2027](https://www.straitstimes.com/singapore/sites-in-mandai-and-upper-jurong-road-to-be-sold-for-purpose-built-dormitories-over-by-end-2027) (~71,500 beds by early 2030s) | 6 | No dormitory query (now added) |
| 09-18 | [JTC/Kajima autonomous excavator/compactor trial, Bulim; deploy ~2028](https://www.straitstimes.com/singapore/construction-robots-on-trial-could-be-deployed-as-early-as-2028) (KTC operators) | 7 | No tech query (now added) |
| 09-28 | [VSMC 300mm fab grand opening, Tampines](https://www.globenewswire.com/news-release/2026/09/28/3369483/0/en/vsmc-celebrates-the-grand-opening-of-its-first-300mm-fab-in-singapore.html) (VIS/NXP JV; 22-month build; ~1,600 jobs) | 4 | No plant query (now added) |
| 09-28 | [MND: Chee Hong Tat, HDB Awards 2026](https://www.mnd.gov.sg/newsroom/speeches/view/speech-by-minister-chee-hong-tat-at-the-hdb-awards-ceremony-2026) — Smart Passenger & Material Hoist (LiDAR/anti-pinch, 1 worker : 3 hoists), hoists + screeding robots at all new BTO sites, STCS | 7 | MND full text skipped as "covered" (now added) |
| 09-28 | [ST cooling gadgets roundup](https://www.straitstimes.com/singapore/environment/solar-powered-air-cons-freeze-tech-and-fan-jakketos-among-innovative-cooling-gadgets-on-the-market) — Freeze Tech cooling wear (up to 9°C) trialled by an SG contractor | 7 | Buried mention (heat-stress query now added; partial) |
| 09-30 | [LTA Tuas Road Viaduct Phase 2 awards](https://www.lta.gov.sg/content/ltagov/en/newsroom/2026/9/news-releases/lta-awards-contracts-for-tuas-road-viaduct-phase-2.html), S$1.2b: Hwa Seng (Pioneer Rd, S$381.6m), CCCC SG (Tuas South Ave 3, S$430.3m), China Harbour (Tuas South Blvd, S$404.4m); works 2027–2032 | 4 | No LTA source (now added) |

Related non-miss (2026-09-21): an ST Jurong Port Road hose-strike death was
already stored via a MustShareNews URL — URL dedup working as designed.
