# Milestone Plan

> Last updated: 2026-03-19

High-level roadmap for the European Football Elo Rating project. Each milestone maps to one or more sprints with detailed plans in `docs/sprint-<N>-plan.md`.

---

## M1: Algorithm Development & EPL Prototype

**Sprints:** 1–3 | **Status:** COMPLETED

Build, tune, and validate the core Elo engine on EPL data, then expand to top-5 European domestic leagues.

| Sprint | Focus | Status |
|--------|-------|--------|
| [Sprint 1](sprint-1-plan.md) | Home advantage, time decay, promoted team init, parameterization | COMPLETED |
| [Sprint 2](sprint-2-plan.md) | MoV scaling, parameter sweep (1,152 combos), engine extraction, tests | COMPLETED |
| [Sprint 3](sprint-3-plan.md) | MoV normalization fix, re-sweep, multi-league ingestion (5 leagues), historical date queries | COMPLETED |

**Key results:**
- `EloEngine` class: tested (60 unit tests), configurable via `EloSettings` + `.env`
- Best parameters: K=20, HA=55, DR=0.90, PE=1400, SP=400 (re-swept after MoV fix)
- Model accuracy: EPL log-loss 0.9772, accuracy 54.4%
- 5 domestic leagues ingested (17,476 matches across EPL, La Liga, Bundesliga, Serie A, Ligue 1)
- Historical date query via `EloEngine.get_ratings_at()`

**Exit criteria:**
- [x] MoV normalization fixed and parameters re-swept
- [x] 5 domestic leagues ingested and rated independently
- [x] Per-league accuracy validated; parameter transferability assessed
- [x] Historical date query API working

---

## M2: Cross-League Calibration

**Sprint:** [4](sprint-4-plan.md) | **Status:** COMPLETED

Source European competition data, normalize competition names/formats across eras, and calibrate ratings across leagues into a single global pool.

**Key results:**
- openfootball chosen as data source: 3,357 European matches (1,968 CL, 814 EL, 575 Conference League)
- 15 CL seasons (2011–2026), 5 EL seasons, 4 Conference League seasons
- Team name normalization: 100+ mappings in `src/team_names.py`, 58/58 top-5 country teams verified
- Competition tier weighting: T1=1.5x (CL knockout), T2=1.2x (CL group/EL knockout), T4/T5=1.0x
- Unified global rankings: 300 teams rated, 20,833 total matches
- Top teams: Bayern Munich & Arsenal (1836), Barcelona (1757), Paris SG (1741), Man City (1721)
- 89 tests passing (60 existing + 29 new European data tests)

**Exit criteria:**
- [x] European cup data ingested and normalized
- [x] Global rating pool running across 5 leagues + European competitions
- [x] Cross-league predictive accuracy validated on CL/EL matches

---

## M3: Data Pipeline & Persistence

**Sprint:** [5](sprint-5-plan.md) | **Status:** COMPLETED

Move from ad-hoc scripts to a production-grade pipeline with persistent storage and automated refresh.

**Key deliverables:**
- **Storage engine ADR** (`docs/adr-storage-engine.md`) — SQLite chosen for operational simplicity
- Database schema with 7 tables: teams, competitions, matches, ratings_history, parameters, fixtures, predictions
- Automated fetch → ingest → rate → persist pipeline (idempotent, logged)
- Match prediction Python API (`predict_match()`, `predict_match_from_db()`)
- Data validation and monitoring (schema drift, completeness, duplicates)

**Key results:**
- SQLite database at `data/elo.db` with WAL mode and foreign keys
- `src/db/` module: connection, schema, repository, seed, validation
- `src/pipeline.py`: idempotent pipeline with duplicate detection
- `src/prediction.py`: match prediction API with database integration
- Fixtures & predictions tables added in Sprint 9

**Exit criteria:**
- [x] Storage engine ADR written and decision made
- [x] Database populated with all historical data
- [x] Pipeline runs end-to-end and is schedulable
- [x] Prediction API returns calibrated probabilities

---

## M4: Web Application

**Sprints:** [6](sprint-6-plan.md)–[8](sprint-8-plan.md) | **Status:** COMPLETED

Ship the user-facing web application — the project's ultimate deliverable.

**Key deliverables:**
- **Frontend tooling ADR** (`docs/adr-frontend-tooling.md`) — Alpine.js + ApexCharts + Tailwind CSS
- FastAPI backend with rankings, team detail, prediction, and search endpoints
- **Comprehensive API documentation** — contract doc, example responses, OpenAPI spec
- Interactive frontend: rankings table, Elo trajectory charts, team detail pages
- **Multi-team comparison chart** — compare up to 10 teams on one chart, league/competition presets
- Match prediction widget (select two teams → win/draw/loss probabilities)
- Historical date explorer (date picker → ratings at any past date)
- Deployment: Docker, CI/CD to Hetzner VPS

| Sprint | Focus | Status |
|--------|-------|--------|
| [Sprint 6](sprint-6-plan.md) | Frontend ADR, FastAPI backend, API documentation, database integration | COMPLETED |
| [Sprint 7](sprint-7-plan.md) | Frontend (rankings, team detail, charts), predictions, historical explorer | COMPLETED |
| [Sprint 8](sprint-8-plan.md) | Prediction page, chart optimization, team stats, Docker/CI, Pydantic fixes | COMPLETED |

**Exit criteria (M4 complete):**
- [x] Web app deployed to Hetzner VPS and publicly accessible
- [x] Rankings, team detail, predictions, and historical queries all working
- [x] API fully documented with contract doc and example responses
- [x] Responsive on mobile and desktop
- [x] CI/CD pipeline: lint → test → build → deploy
- [x] Rich team profile pages with stats card and Elo-enriched results
- [x] Smooth chart interactions (updateSeries instead of destroy/recreate)

---

## M4.5: Advanced Chart Features & Export

**Sprints:** 27 | **Status:** PARTIALLY COMPLETE

Further enhance ApexCharts visualizations with export and preset features deferred from Sprints 7-8.

**Completed (in Sprints 7-8):**
- ~~Zoom and pan~~: ApexCharts native zoom/pan (Sprint 7)
- ~~Date range selection~~: noUiSlider double-ended slider (Sprint 7)
- ~~Multi-team overlay~~: Up to 10 teams on one chart (Sprint 7)
- ~~Chart performance optimization~~: updateSeries instead of destroy/recreate (Sprint 8)

**Remaining scope:**
- **Export functionality**: Download chart as PNG or CSV
- **Chart presets**: Quick filters (e.g., "Last season", "All time", "CL campaigns only")
- **Comparison snapshots**: Save and share chart configurations

**Depends on:** M4 (complete)

**Exit criteria:**
- [ ] Export chart as PNG, SVG, and CSV
- [ ] Chart presets for common time ranges
- [ ] Shareable chart configurations (URL-encoded or saved to DB)

---

## M5: Advanced Parameter Optimization

**Sprints:** 24 | **Status:** NOT STARTED

Replace the brute-force grid sweep with a principled optimization framework. The current `param_sweep.py` tests a fixed grid of ~1,000 combinations — this doesn't scale as the parameter space grows (per-league tuning, tier weights, MoV coefficients).

**Scope:**
- Bayesian optimization (e.g., Optuna, scikit-optimize) to efficiently search the parameter space
- Per-league parameter tuning — test whether a single global parameter set is optimal or if leagues benefit from individual tuning
- Cross-validation framework: proper train/test splits by season, out-of-sample evaluation
- Multi-objective optimization: balance log-loss, Brier score, and accuracy rather than picking one
- Sensitivity analysis: which parameters matter most, which are noise
- Confidence intervals on optimal parameter values (bootstrap or similar)
- Automated re-tuning pipeline: when new season data arrives, re-optimize and flag if parameters drift significantly

**Depends on:** M1 (algorithm finalized), M3 (pipeline for automated re-runs)

**Key questions to resolve:**
- Single global parameter set vs. per-league parameters vs. per-competition-tier parameters?
- How much historical data to use for training? (all 10+ years, or rolling window?)
- Should tier weights (M2) be optimized jointly with base Elo parameters?

**Exit criteria:**
- [ ] Optimization framework replacing grid sweep
- [ ] Per-league vs. global parameter decision made with evidence
- [ ] Out-of-sample validation on held-out seasons
- [ ] Automated re-tuning integrated into pipeline

---

## M6: Full UEFA League Coverage

**Sprints:** 25–26 | **Status:** NOT STARTED

Expand from top-5 leagues to all UEFA member association domestic leagues. This is a data scale and normalization challenge — the Elo engine itself should work unchanged.

**Scope:**
- Ingest domestic top-flight leagues for all 55 UEFA member associations
- Handle data quality variation: smaller leagues may have incomplete records, inconsistent team names, fewer seasons available
- Promoted/relegated team handling across tiers within a country (e.g., Championship → EPL)
- Second-tier league support for major nations (Championship, 2. Bundesliga, Serie B, etc.) — enables proper promoted team rating inheritance instead of the current heuristic
- Data source strategy: Football-Data.co.uk covers ~25 leagues; openfootball and other sources needed for the rest
- Scalability: ensure pipeline and database handle ~55 leagues × 10 seasons without performance issues
- Frontend: league browser/selector that handles 55+ leagues cleanly (grouping by UEFA coefficient tier, country, or region)

**Depends on:** M2 (cross-league calibration working), M3 (pipeline can handle multi-league ingestion), M4 (frontend can display it)

**Key questions to resolve:**
- Minimum data quality threshold — how many seasons/matches required before including a league?
- Should small leagues (e.g., Faroe Islands, San Marino) use the same parameters as top-5 leagues?
- How to handle leagues with fewer than 10 teams or split seasons?
- Cross-tier calibration within a country (Championship teams meeting EPL teams in cups)

**Exit criteria:**
- [ ] All 55 UEFA top-flight leagues ingested (where data available)
- [ ] Second-tier leagues for at least the top-5 nations
- [ ] Data quality report per league (coverage, completeness, known gaps)
- [ ] Frontend handles full league catalogue without UX degradation
- [ ] Promoted team ratings inherited from lower-tier league data where available

---

## M7: Two-Leg Tie Modeling

**Sprints:** 23 | **Status:** NOT STARTED

Decide how the Elo engine treats two-leg playoff ties (home and away) that appear throughout European competitions and some domestic cups. The current engine processes every row as an independent match, but two-leg ties are structurally linked — the second leg is played under the context of the first-leg result (aggregate score, away goals rule pre-2021, extra time/penalties).

**Core question:** Treat as two independent matches, a single aggregate match, or a hybrid?

| Approach | Pros | Cons |
|----------|------|------|
| **Two independent matches** (status quo) | Simple, no special handling, preserves home/away distinction per leg | Ignores tactical context — a team "losing" 0-1 at home in leg 2 after winning 3-0 away may not be truly underperforming |
| **Single aggregate match** | Captures the tie outcome faithfully, avoids penalizing dead-rubber legs | Loses per-leg home/away signal, halves the number of data points |
| **Hybrid: independent matches with reduced K** | Keeps both data points, dampens noise from dead-rubber legs | Requires identifying which matches are part of a tie and tuning a K discount factor |
| **Hybrid: independent + aggregate bonus** | Full per-leg updates plus a small bonus/penalty for the tie winner/loser | Most information-rich, but most complex to implement and tune |

**Scope:**
- Audit where two-leg ties appear: CL/EL knockout rounds, Conference League, domestic cup semis/finals (League Cup, Copa del Rey, etc.), promotion playoffs
- Determine whether second legs show measurably different Elo prediction accuracy vs. first legs (dead-rubber effect)
- Prototype each approach and compare predictive accuracy on historical CL knockout data
- Handle edge cases: extra time, penalty shootouts (count as draw for Elo?), away goals rule era vs. post-2021
- Document decision as ADR

**Depends on:** M2 (European cup data available with round/leg metadata)

**Key questions to resolve:**
- Is leg metadata reliably available in the data sources? (first leg vs. second leg, aggregate score)
- How large is the dead-rubber effect empirically?
- Should penalty shootout outcomes affect Elo at all, or only the 90/120-min result?
- Does the answer differ by competition tier (CL knockout vs. domestic cup)?

**Exit criteria:**
- [ ] Empirical analysis of two-leg tie prediction accuracy (status quo vs. alternatives)
- [ ] ADR documenting the chosen approach with evidence
- [ ] Engine updated if approach differs from status quo
- [ ] Edge cases (extra time, penalties, away goals rule) handled consistently

---

## M8: Live Data & Fixtures

**Sprints:** [9](sprint-9-plan.md)–[11](sprint-11-plan.md) | **Status:** COMPLETED | **Priority:** HIGH

Transition from historical-only data to quasi-live updates with upcoming fixtures and completed match results.

**Groundwork completed (Sprint 9):**
- ADR-004: football-data.org selected as live data source (`docs/adr-004-live-data-source.md`)
- Database schema: fixtures & predictions tables with CRUD functions
- 2010-2016 warm-up period for calibration (display_from_date filtering)

**Implementation completed (Sprint 10):**

### 8a. Data Persistence & Deployment Strategy ✅
- **DB as persistent state**: `elo.db` removed from git, treated as volume-mounted persistent data
- **Schema migrations**: Numbered migration system (`src/db/migrate.py`) with 4 migrations
- **Seed vs. incremental separation**: `run_pipeline()` for cold-start; `run_incremental_update()` for live data
- **DB backup on deploy**: `scripts/backup_db.sh` with WAL-safe backup and 5-copy rotation
- **CI/CD updated**: backup → migrate → incremental update → health check

### 8b. Data Source Integration ✅
- **football-data.org API client**: Async client with token-bucket rate limiting (10 req/min), 3 retries, exponential backoff
- **Team ID mapping**: 150+ known name mappings + fuzzy matching fallback for 325 teams
- **Recent results API**: `fetch_and_ingest_matches()` fetches FINISHED matches from last 14 days
- **Data freshness policy**: `scripts/run_daily_update.py` for 2x daily cron

### 8c. Pipeline Automation (partially complete)
- **Scheduled fetch**: Cron-ready script (`scripts/run_daily_update.py`) ✅
- **Incremental rating updates**: `run_incremental_update()` appends new matches, recomputes ratings ✅
- **Match result validation**: Skips TBD teams, handles API errors gracefully per competition ✅
- **Dockerized cron**: Bake cron schedule into Docker image so daily updates run automatically in production — **Sprint 11**

### 8d. Fixtures Frontend ✅
- **Fixtures page**: `/fixtures` with upcoming matches grouped by competition
- **Elo predictions**: Pre-match probability bars (home/draw/away)
- **Competition filters**: Alpine.js interactive filtering

**Exit criteria:**
- [x] Database survives deployments without data loss
- [x] Schema migrations apply cleanly on existing databases
- [x] Upcoming fixtures fetched and displayed in frontend
- [x] Completed matches auto-ingested within 24 hours
- [x] Ratings updated automatically after new results
- [x] API rate limits and costs acceptable for production
- [x] Daily update cron baked into Docker image (Sprint 11)

---

## M9: Prediction Tracking & Validation

**Sprints:** 9–11 (backend + frontend), TBD (backfill) | **Status:** PARTIALLY COMPLETE | **Priority:** MEDIUM

Track predictions made by the system and compare them to actual outcomes, enabling performance monitoring and user transparency.

**Completed (Sprint 9):**
- Predictions table with CRUD functions (insert_prediction, get_predictions_for_fixture)
- CHECK constraint ensuring exactly one of match_id/fixture_id is set

**Completed (Sprint 10):**
- Auto-insert predictions for upcoming fixtures during ingestion
- Brier score computation (`src/live/prediction_tracker.py`)
- `/api/prediction-accuracy` endpoint with aggregate stats, calibration buckets, per-competition breakdown
- `brier_score` and `scored_at` columns added to predictions table (migration 004)

### 9a. Prediction Automation ✅
- Auto-insert predictions for upcoming fixtures when fetched
- After match completes: compare prediction vs result, compute Brier score

**Completed (Sprint 11):**
- Prediction history page (`/prediction-history`) with pagination, filters, Brier coloring
- Accuracy dashboard (`/accuracy`) with calibration chart, Brier trend, per-competition breakdown
- Navigation links added to all pages

**Remaining scope:**

### 9a.1. Prediction Accuracy Debugging ✅ (Sprint 14)
- **Root cause:** `score_completed_matches()` was never called in `run_daily_update()`, and fixture status was never updated to `completed` when matches were ingested
- **Fix:** Added scoring call to daily update pipeline, added fixture status transition on match ingestion

### 9a.2. Daily Update 403 Retry ✅ (Sprint 14)
- **Fix:** Split 401/403 handling in `FootballDataClient._request()` — 401 raises immediately, 403 retries with escalating delays (10s, 60s, 120s)

### 9b. Historical Prediction Backfill ✅ (Sprint 14)
- **Solution:** `scripts/backfill_predictions.py` replays Elo computation chronologically, captures pre-match ratings, generates predictions for all post-2016 matches
- **Results:** 20,263 backfilled predictions with Brier scores (mean Brier: 0.586), `source='backfill'` column distinguishes from live predictions
- **Schema:** Migration 005 adds `source` column to predictions table
- **Frontend:** Accuracy dashboard shows by-source breakdown (Live vs Backfill badges), prediction history includes source field

### 9c. Performance Metrics (partial)
- ~~Accuracy tracking~~: Brier score tracked ✅
- ~~Calibration curves~~: Calibration chart on accuracy dashboard ✅
- ~~Dashboard~~: Accuracy dashboard with summary cards, trend, per-competition breakdown ✅
- **Alerts**: Flag if model performance degrades below threshold

### 9d. User-Facing Features
- ~~Prediction history page~~: `/prediction-history` with scored predictions ✅
- **Accuracy badge**: Display model's recent accuracy on prediction widget
- **Confidence intervals**: Show uncertainty around predictions

**Depends on:** M8 (complete), M4 (complete)

**Exit criteria:**
- [x] All predictions stored in database before matches
- [x] Prediction accuracy dashboard live (Sprint 11)
- [x] Users can view prediction history and outcomes (Sprint 11)
- [x] Brier score tracked over time
- [x] Prediction scoring pipeline working end-to-end (live predictions scored after match completion) — Sprint 14
- [x] Daily update retries on HTTP 403 (3 attempts: 10s, 60s, 120s delays) — Sprint 14
- [x] Historical predictions backfilled so dashboard is populated on fresh deploy (20,263 predictions) — Sprint 14

---

## M10: Initial Elo Calibration Fix

**Sprint:** [9](sprint-9-plan.md) | **Status:** COMPLETED

Fix the issue where all teams at the start of the dataset are initialized to the same rating instead of contextually appropriate ratings.

**Approach chosen:** Warm-up period

**Key results (Sprint 9):**
- Extended data ingestion back to 2010 (6 extra seasons × 5 leagues = 30 CSV files)
- Added `display_from_date` to EloSettings (default "2016-08-01", env-configurable)
- Seasons 2010-2016 serve as warm-up — ratings computed but hidden from public display
- API endpoints filter by display_from_date (team history, peak/trough stats)
- Validation: Aug 2016 starting ratings — Barcelona 1813, Real Madrid 1805, Bayern 1801
- 31,789 total matches (up from 20,833), 325 teams, 63,578 rating entries

**Exit criteria:**
- [x] Historical data back to 2010 ingested
- [x] Warm-up period runs before public display window
- [x] 2016 starting ratings validated against reasonable expectations
- [x] `display_from_date` implemented and filtering all API endpoints
- [x] No team starts at exactly 1500 unless genuinely unknown

---

## M11: UI Redesign — "EloKit"

**Sprints:** [12](sprint-12-plan.md), [12.1](sprint-12.1-plan.md) | **Status:** COMPLETED

Complete UI redesign replacing multi-page layout with a single unified "EloKit" layout. All contexts (global, nation, league, team) share the same page structure with content scoped to the navigation context.

**Key deliverables:**

### Sprint 12 — Core Redesign ✅
- **Unified layout**: Single `index.html` replaces 8 separate templates
- **URL scheme**: `/{nation}/{league}/{team}` — hierarchical context-aware routing
- **Sidebar navigation**: Nations → leagues/cups, European competitions, hamburger on mobile
- **4 content sections**: Fixtures, Accuracy widget, Elo history chart, Rankings table
- **Context-aware API endpoints**: `/api/fixtures/scoped`, `/api/chart/scoped`, `/api/accuracy/scoped`, `/api/rankings/context`, `/api/sidebar`
- **Slug resolution**: URL-safe slugs for nations, competitions, and teams
- **EloKit branding**: Logo, generic icons (club, league, cup), breadcrumb navigation
- Old templates retired, old routes redirect to new equivalents

### Sprint 12.1 — Polish & Bug Fixes ✅
- **Data loading regression fix**: Nested `<button>` inside `<button>` broke DOM tree; nested `x-data` scoped state incorrectly
- **Fixtures pagination**: 3 finished + 3 upcoming by default, "Load more..." with offset-based pagination
- **Rankings display**: Top 5 + team context (±3 surrounding teams) with "View all" toggle
- **Chart team management**: Add/remove teams via search, zoom controls, `chart.updateOptions()` for live series updates
- **Banner**: "Club Rating Analytics" inline in header

**Exit criteria:**
- [x] Single unified layout for all 4 context levels (global, nation, league, team)
- [x] Sidebar navigation with nations, leagues, and European competitions
- [x] Fixtures, accuracy, chart, and rankings all scope correctly to context
- [x] EloKit branding throughout
- [x] Mobile responsive with hamburger sidebar
- [x] Existing API endpoints backward compatible
- [x] All 360 tests passing, no regressions
- [x] Old templates removed, old URLs redirect

---

## M12: Flags & Logos

**Sprints:** 13 (nations/competitions), TBD (clubs) | **Status:** PHASE 1 COMPLETE | **Priority:** MEDIUM

Add visual identity assets — country flags, league/cup competition logos, and club crests — to enrich the UI throughout EloKit.

### Phase 1: Nation Flags & Competition Logos (Sprint 13) ✅
- **Country flags**: 6 SVG flags (flag-icons, MIT) in sidebar and breadcrumbs
- **League logos**: Minimal styled SVG badges for 5 domestic leagues (PL, LL, BL, SA, L1)
- **Cup competition logos**: CL, EL, Conference League SVG badges
- **Integration points**: Sidebar nav items, breadcrumbs, fixtures match cards
- **API**: `flag_url` on `SidebarNation`, `logo_url` on `SidebarCompetition`, `competition_logo_url` on `ScopedFixtureEntry`
- **364 tests passing** (4 new tests for URL fields)

### Phase 2: Club Logos (Future)
- **Club crests**: Fetch logos for all 325+ teams
- **Integration points**: Rankings rows, team detail header, chart legends, fixtures match cards
- **Data source**: TBD — evaluate football-data.org API (crest URLs), Wikipedia/Wikidata, or curated asset set
- **Fallback**: Generic club icon (existing) for teams without logos

**Depends on:** M11 (EloKit layout — integration points exist)

**Key questions to resolve:**
- Data source and licensing for flags (e.g., flagcdn.com, country-flags npm, bundled SVGs)?
- Data source for league/cup logos (official assets, Wikipedia, curated)?
- Data source for club crests (football-data.org API provides `crestUrl`, Wikipedia)?
- Bundle assets locally vs. CDN/hotlink vs. store in DB?

**Exit criteria:**
- [x] Nation flags displayed in sidebar and breadcrumbs
- [x] League and cup logos displayed in sidebar and fixtures
- [ ] Club crests displayed in rankings, fixtures, and team pages (Phase 2)
- [x] Graceful fallback for missing assets (generic icons)
- [x] Assets load fast (SVG preferred)

---

## M13: Detailed Prediction Accuracy View

**Sprints:** 15 (core accuracy view), 15.1 (charts, Elo deltas, polish) | **Status:** COMPLETED | **Priority:** HIGH

The EloKit accuracy widget shows a compact summary (total predictions, Brier score, accuracy %, trend) with an inline "View all" expansion that displays by-source and per-competition breakdown. However, the "View all" link is non-functional, and the existing `/api/prediction-accuracy` endpoint already returns rich data (calibration buckets, time series, median Brier) that isn't rendered anywhere in the EloKit UI. The old dedicated `/accuracy` and `/prediction-history` pages were retired in Sprint 12's EloKit redesign and never rebuilt within the unified layout.

**Scope:**

### 13a. Fix "View all" Accuracy Link ✅ (Sprint 15)
- "View details" link opens dedicated accuracy detail panel within EloKit
- `accuracyView: 'compact' | 'detail'` state toggle with back link
- Parallel fetch of grid, history, and expanded detail on open

### 13b. Calibration Visualization
- **Calibration chart**: Render the 10-bucket calibration data from `/api/prediction-accuracy` as a visual chart (predicted probability vs. actual outcome rate)
- **Perfect calibration reference line**: Diagonal reference showing ideal calibration
- Uses existing `calibration` field from `PredictionAccuracyResponse`

### 13c. Brier Score Time Series
- **Rolling Brier trend chart**: ApexCharts line/area chart showing Brier score evolution over time
- Uses existing `time_series` field from `PredictionAccuracyResponse`
- Allows users to see if model performance is improving or degrading

### 13d. Prediction History Integration ✅ (Sprint 15)
- **Match Prediction Log**: Paginated, searchable table of all scored predictions
- **Multi-word team search**: Whitespace-separated tokens matched across home+away team names (debounced 300ms)
- **Rich columns**: Date, match (with score), competition, probability bars (H/D/A), result badge, Brier score (color gradient), source badge (Live/Backfill)
- **Correct prediction highlighting**: Subtle green row background for correct predictions
- **Pagination**: Server-side with prev/next, "Page X of Y", resets on new search

### 13d.1. Prediction Performance Grid ✅ (Sprint 15)
- **3×3 confusion matrix**: Predicted outcome (H/D/A) vs actual outcome with counts and percentages
- **API endpoint**: `GET /api/accuracy/grid` with country, competition, team_id, source scoping
- **Heatmap styling**: Green diagonal (correct), gray off-diagonal, intensity scales with percentage
- **Row totals and grand total** with accuracy percentage
- **Responsive**: Abbreviated labels (H/D/A) on mobile

### 13e. Context-Aware Scoping ✅ (Sprint 15)
- All accuracy detail views respect the current navigation context (global, nation, league, team)
- Extended `/api/prediction-accuracy` with `country` and `team_id` filters (backward compatible)
- Extended `/api/prediction-history` with `search`, `country`, and `team_id` filters

### 13f. API Contract Documentation Update (Sprint 15.1)
- **Review and update** `docs/api-contract.md` to cover all current endpoints (currently only documents 7 original Sprint 6 endpoints)
- **Missing endpoints**: `/api/fixtures/scoped`, `/api/chart/scoped`, `/api/accuracy/scoped`, `/api/rankings/context`, `/api/sidebar`, `/api/prediction-accuracy`, `/api/prediction-history`, `/api/accuracy/grid`, `/api/team-stats/{team_id}`
- **Update data coverage stats**: 325 teams, 31,789 matches, 2010-2026 (was 300/20,833/2015-2026)
- **Document new query parameters**: search, country, team_id scoping across accuracy and history endpoints
- **Update changelog** with Sprints 7-15 additions
- **Role:** `/tech-writer`

### 13g. Elo Change on Completed Fixtures
- **Elo delta display**: Show Elo rating change (e.g., +12 / -8) for each team on completed match cards in the fixtures widget
- Requires exposing pre-match and post-match Elo ratings (or the delta) from the API for completed matches
- Extend `/api/fixtures/scoped` response to include `home_elo_change` and `away_elo_change` fields on completed fixtures
- Color-coded: green for positive, red for negative

### 13h. Logo & Breadcrumb Polish (M12 follow-up)
- **Increase logo sizes**: Sidebar and breadcrumb logos from 20×20 to 30×30 pixels
- **Breadcrumb logos for all levels**: Show competition logo and nation flag at every breadcrumb segment (currently only nation flag shown in breadcrumbs; competition logo missing at league/team levels)

**Depends on:** M9 (prediction tracking complete), M11 (EloKit layout), M12 (flags & logos)

**Exit criteria:**
- [x] "View all" link on accuracy widget navigates to/renders detailed accuracy view (Sprint 15)
- [x] Calibration chart rendered from existing API data (Sprint 15.1)
- [x] Brier score time series chart visible (Sprint 15.1)
- [x] Prediction history browsable within EloKit (with pagination and filters) (Sprint 15)
- [x] All views scoped to current navigation context (Sprint 15)
- [x] Existing 20,263+ predictions displayed with source labels (Sprint 15)
- [x] 3×3 Prediction Performance Grid with heatmap styling (Sprint 15)
- [x] Multi-word team search across home+away names (Sprint 15)
- [x] 388 tests passing (24 new, no regressions) (Sprint 15)
- [x] API contract doc updated to cover all 17 endpoints (Sprint 15.1)
- [x] All logos increased in size (sidebar, breadcrumbs, fixtures) (Sprint 15.1)
- [x] Breadcrumbs show flag/logo at every navigation level (Sprint 15.1)
- [x] Completed fixture cards show Elo change per team (color-coded +/-) (Sprint 15.1)

---

## M14: Momentum Metric

**Status:** DEPRIORITIZED (research complete 2026-03-19) | **Priority:** LOW

Track and display an "Elo momentum" metric — an exponentially weighted moving average (EWMA) of recent Elo rating changes, intended to capture whether a team is trending up or down independent of their absolute rating.

### Research findings (2026-03-19)

Two architectures were tested against 20,263 scored predictions (display period 2016-2026):

**Architecture A: Additive Elo adjustment** — momentum adjusts effective Elo before recomputing probabilities.
- Best improvement: **+0.000%** (no change vs baseline)

**Architecture B: Independent predictor + linear blend** — momentum generates a separate 3-way probability distribution (Davidson logistic model) blended with Elo probabilities via `P = α·P_elo + (1-α)·P_momentum`.
- Grid searched 240 combinations per momentum config (α, spread, draw steepness)
- Best result: **−0.38%** (momentum blend is worse than pure Elo)
- Pure momentum predictor in isolation: LL=1.265 vs Elo 0.988 (~28% worse)

**Momentum does correlate with outcomes** (home-win matches show positive momentum differential, away-win matches show negative) — but Elo already encodes this information. Adding momentum double-counts recent performance already reflected in ratings.

**Consistent with academic literature**: Hvattum & Arntzen (2010) found form variables add minimal predictive power beyond Elo in football.

### Possible future scope (display-only)

Momentum could be shown as a UX feature — "Teams in Form" ranking, per-team trend indicator — without affecting predictions. Implementation cost is low (compute during daily update, expose via API).

**Formula:**
```
Momentum = Σ[i=0..N-1] w(i) · Δ_elo(i)
w(i) = λ^i / Σλ^j   (most recent match has highest weight)
Recommended: λ=0.85, N=10
```

**Not recommended**: using momentum in match probability calculations.

**Research code:** `notebooks/momentum_blend_validation.py`, `notebooks/momentum_research_optimized.py`
**Research report:** `docs/momentum-research-summary.md`

**Exit criteria (if display-only feature pursued):**
- [ ] Momentum computed during daily update and stored in DB
- [ ] `GET /api/teams/{team_id}/momentum` endpoint
- [ ] "Teams in Form" widget on EloKit global/league context
- [ ] **Not** used in `/api/prediction` probability calculations

---

## M15: Per-Competition Elo Contribution

**Sprint:** 16 | **Status:** NOT STARTED | **Priority:** MEDIUM

A team's global Elo rating is the cumulative result of all matches across every competition they've played. This milestone adds a **per-competition Elo contribution breakdown** — showing how much of a team's rating change was earned (or lost) in each competition, per season or all-time.

**Example:** Liverpool in 2024-25
- Premier League: −18 (disappointing domestic form)
- Champions League: +34 (strong European campaign)
- League Cup: +5 (early rounds)

### No Schema Changes Required

The data already exists via the `ratings_history → matches → competitions` JOIN:

```sql
SELECT c.name, c.tier, SUM(rh.rating_delta) AS elo_contribution,
       COUNT(*) AS matches_played
FROM ratings_history rh
JOIN matches m ON m.id = rh.match_id
JOIN competitions c ON c.id = m.competition_id
WHERE rh.team_id = ? AND rh.date >= ?
GROUP BY c.id
ORDER BY elo_contribution DESC
```

### Scope

**15a. API Endpoint**
- `GET /api/teams/{team_id}/competition-breakdown?season=2024-25`
- Default: current season. Season selector uses `YYYY-YY` format.
- `all_time=true` param for cumulative lifetime contribution
- Returns: `[{competition, tier, elo_contribution, matches_played, wins, draws, losses}]`

**15b. Frontend Widget — Team Context**
- Horizontal bar chart in the team detail view (when URL is `/{nation}/{league}/{team}`)
- Competitions as rows, Elo contribution as colored bars (green for positive, red for negative)
- Season selector dropdown with "All time" option

**15c. Stage Weighting Enhancement (sub-feature, future)**
- Current: T1=CL knockout (1.5×), T2=CL group (1.2×) — already stage-aware
- Possible future enhancement: split within knockout rounds (R16=1.3×, QF=1.4×, SF=1.5×, Final=1.6×)
- Requires tagging match stage in `src/european_data.py` and re-running the full pipeline
- **Treat as a separate research sprint** akin to M7

**Depends on:** M4 (web app), M11 (EloKit layout), M3 (ratings_history with match_id)

**Exit criteria:**
- [ ] `GET /api/teams/{team_id}/competition-breakdown` returns per-competition Elo deltas
- [ ] Season filtering works (default current season, `all_time=true` for cumulative)
- [ ] Frontend widget in team context with season selector
- [ ] API contract doc updated
- [ ] Tests added for new endpoint

---

## M16: Monte Carlo Season Simulation

**Sprint:** 18 | **Status:** NOT STARTED | **Priority:** HIGH

Simulate the remainder of the current season using Elo win probabilities to produce a probability distribution over final league standings for every team. Users can see each club's likelihood of winning the title, qualifying for European competition, or getting relegated.

**Scope:**
- For each remaining fixture in a league, sample match outcomes (H/D/A) from the current Elo-derived probabilities
- Run N iterations (e.g., 10,000) to build a distribution over final points totals and table positions
- Aggregate results: `P(champion)`, `P(top 4)`, `P(relegated)` per team
- `GET /api/simulations/{competition_slug}` — returns current-season simulation results (cached, refreshed on daily update)
- Frontend: league context shows a simulation table with probability columns alongside current standings

**Depends on:** M4 (web app), M8 (live fixtures), M11 (EloKit)

**Key questions to resolve:**
- How to handle matches already played mid-simulation run vs. remaining-only?
- Cache invalidation: re-run simulation after each daily update or on demand?
- Draw probability treatment: use existing three-way Elo prediction directly?

**Exit criteria:**
- [ ] Monte Carlo simulation runs for all 5 domestic leagues (current season)
- [ ] `GET /api/simulations/{competition_slug}` returns position probabilities per team
- [ ] Frontend simulation table in league context
- [ ] Simulation results refreshed as part of daily update pipeline
- [ ] Tests added for simulation logic and endpoint

---

## M17: Upset Index & Historical Upsets Log

**Sprint:** 17 | **Status:** NOT STARTED | **Priority:** MEDIUM

Rank all historical matches by the size of the Elo upset — matches where a large underdog won. Surface the biggest upsets in the dataset as an engaging editorial feature.

**Scope:**
- Upset score: Elo differential between winner and loser at time of match (pre-match ratings already in `ratings_history`)
- `GET /api/upsets?top=50&competition=...&season=...` — returns top-N biggest upsets with match details and Elo context
- Frontend: "Biggest Upsets" widget on global/league/competition context pages, sortable table
- Optional: per-team "biggest upsets caused" stat on team context

**Depends on:** M3 (ratings_history with pre-match data), M4 (web app), M11 (EloKit)

**Key questions to resolve:**
- Use absolute Elo difference or implied probability swing as the upset metric?
- Include draws as partial upsets when a heavy favourite fails to win?

**Exit criteria:**
- [ ] `GET /api/upsets` endpoint with competition and season filters
- [ ] Frontend upsets widget on global and league contexts
- [ ] Pre-match Elo differential computable from `ratings_history` for all backfilled matches
- [ ] Tests added for endpoint and ranking logic

---

## M18: Expected Goals (xG) Elo Updates

**Sprint:** 22 | **Status:** NOT STARTED | **Priority:** MEDIUM

Replace raw match result (W/D/L) with expected goals (xG) as the signal for Elo updates. A team that loses 1-0 despite generating 3.2 xG vs 0.4 xG should be penalised less than a team that was genuinely outplayed.

**Scope:**
- Source xG data: football-data.org free tier does not include xG; evaluate Understat (scrape), StatsBomb open data, or FBref
- Modify `EloEngine.elo_update()` to accept optional xG values; derive an "xG result" (xG-weighted H/D/A or continuous score)
- Validate: compare Brier score on held-out seasons for xG-Elo vs. current goals-based Elo
- Document decision as ADR

**Depends on:** M1 (algorithm), M3 (pipeline)

**Key questions to resolve:**
- Data source availability and coverage for all 5 leagues + European competitions?
- How to handle matches with missing xG (fall back to goals)?
- Treat xG result as continuous score or discretise to H/D/A?
- Does xG signal add meaningful predictive power beyond MoV scaling already in place?

**Exit criteria:**
- [ ] xG data sourced for at least the top-5 domestic leagues (2016-present)
- [ ] `elo_update()` extended with optional xG input (backward compatible)
- [ ] Held-out Brier score comparison (xG-Elo vs. current) documented
- [ ] ADR written with decision and evidence
- [ ] Tests cover xG path and fallback to goals

---

## M19: Public REST API

**Sprint:** 20 | **Status:** NOT STARTED | **Priority:** MEDIUM

Make the existing `/api/*` endpoints publicly accessible with basic rate limiting and optional API key authentication, so developers and analysts can build on top of EloKit ratings.

**Scope:**
- API key issuance: simple static key table in DB or env-configured allow-list (no OAuth)
- Rate limiting: per-key or per-IP token bucket (reuse existing token-bucket pattern from `src/live/`)
- Public documentation: expose `/api/docs` (FastAPI OpenAPI) publicly; update `docs/api-contract.md` with auth instructions
- Decide which endpoints are public (rankings, team ratings, predictions) vs. internal-only (admin, pipeline triggers)
- CORS: allow all origins for public read endpoints

**Depends on:** M4 (web app), M6 (full league coverage is a prerequisite for a compelling public API)

**Key questions to resolve:**
- Key issuance flow: self-serve signup page vs. email-based vs. fully open (no auth)?
- Rate limit tiers: anonymous vs. keyed?
- Which endpoints remain internal (e.g., pipeline trigger)?

**Exit criteria:**
- [ ] Rate limiting applied to all public API endpoints
- [ ] Optional API key header accepted and validated
- [ ] `/api/docs` (OpenAPI UI) publicly accessible
- [ ] `docs/api-contract.md` updated with auth and rate-limit details
- [ ] At least one usage example (curl / Python snippet) in the docs

---

## M20: Head-to-Head Historical Analysis

**Sprint:** 17 | **Status:** NOT STARTED | **Priority:** MEDIUM

Select any two teams and view their historical head-to-head record enriched with Elo context: record (W/D/L), Elo differential over time, and how the Elo-predicted win probability has evolved across their meetings.

**Scope:**
- `GET /api/h2h?team_a={id}&team_b={id}&season=...` — returns all H2H matches with pre-match Elo ratings, predicted probabilities, and actual results
- Summary stats: W/D/L record, average Elo differential, biggest upset (by Elo)
- Frontend: H2H widget accessible from the team prediction widget (after selecting two teams)
- Chart: Elo rating of both teams plotted over time with H2H match markers

**Depends on:** M4 (prediction widget), M11 (EloKit), M3 (ratings_history)

**Exit criteria:**
- [ ] `GET /api/h2h` endpoint returning H2H matches with Elo context
- [ ] W/D/L summary and average Elo differential
- [ ] Frontend H2H panel accessible from the prediction widget
- [ ] Tests added for endpoint and history retrieval

---

## M21: Undervalued / Overvalued Team Metric

**Sprint:** 19 | **Status:** NOT STARTED | **Priority:** LOW

Surface teams whose recent results don't match their Elo rating — e.g., a team on a 6-game winning streak whose Elo has barely moved because they've been beating weak opponents. Conversely, a high-Elo team losing form. Framed as an editorial "hidden gems / overrated clubs" stat.

**Scope:**
- Metric: compare a team's recent actual points-per-game (last N matches) vs. Elo-implied expected points-per-game against the same opponents
- Positive gap (outperforming Elo expectations) → "undervalued"; negative gap → "overvalued"
- `GET /api/teams/{team_id}/performance-vs-expectation?n=10` — returns the gap metric with match-level breakdown
- Frontend: "Undervalued / Overvalued" widget on global or league context, sortable table

**Note:** Research has shown momentum (recent Elo delta EWMA) adds no predictive value (M14). This metric is explicitly a display/editorial feature — **not** used in match probability calculations.

**Depends on:** M4, M8 (live fixtures for current-season results), M11 (EloKit)

**Exit criteria:**
- [ ] Performance-vs-expectation metric computed for all teams
- [ ] `GET /api/teams/{team_id}/performance-vs-expectation` endpoint
- [ ] Global/league context widget listing teams by gap
- [ ] **Not** used in prediction probability calculations
- [ ] Tests added

---

## Sprint Roadmap

| Sprint | Milestones | Focus | Status |
|--------|-----------|-------|--------|
| 1–3 | M1 | Algorithm, multi-league, parameter tuning | COMPLETED |
| 4 | M2 | Cross-league calibration, European data | COMPLETED |
| 5 | M3 | Data pipeline, SQLite, persistence | COMPLETED |
| 6 | M4 | FastAPI backend, API documentation | COMPLETED |
| 7 | M4, M4.5 (partial) | Frontend, charts, comparison, zoom/pan | COMPLETED |
| 8 | M4 | Prediction page, Docker/CI, chart perf | COMPLETED |
| 9 | M10, M8 (groundwork), M9 (groundwork) | Calibration fix, fixtures/predictions schema, ADR-004 | COMPLETED |
| **10** | **M8, M9 (partial)** | **Data persistence, live API client, ingestion pipeline, fixtures page, prediction tracking** | **COMPLETED** |
| **11** | **M8, M9 (partial)** | **Dockerized daily update cron, prediction accuracy dashboard, prediction history frontend** | **COMPLETED** |
| **12** | **M11** | **EloKit UI redesign — unified layout, sidebar nav, context-aware routing** | **COMPLETED** |
| **12.1** | **M11** | **EloKit polish — data loading fix, fixtures pagination, chart controls, rankings display** | **COMPLETED** |
| **13** | **M12** | **Nation flags, league/cup competition logos** | **COMPLETED** |
| **14** | **M9 (9a.1, 9a.2, 9b)** | **Prediction scoring pipeline fix, 403 retry, historical prediction backfill (20,263 predictions)** | **COMPLETED** |
| **15** | **M13 (13a, 13d, 13d.1, 13e)** | **Detailed accuracy view: Prediction Performance Grid, searchable Match Prediction Log, context-aware scoping** | **COMPLETED** |
| **15.1** | **M13 (13b–c, 13f–h)** | **Calibration chart, Brier time series, API contract doc update, Elo change on fixtures, logo & breadcrumb polish** | **COMPLETED** |
| **15.2** | **M9, M13** | **Bug fixes: Brier trend time axis (use match date), prediction history empty in non-team scopes** | **COMPLETED** |
| **16** | **M15** | **Per-competition Elo contribution breakdown (team context widget + API)** | **PLANNED** |
| **17** | **M17, M20** | **Upset Index (biggest upsets by Elo diff) + Head-to-head historical analysis** | **PLANNED** |
| **18** | **M16** | **Monte Carlo season simulation — title/top-4/relegation probabilities** | **PLANNED** |
| **19** | **M21** | **Undervalued/overvalued team metric (display only, editorial feature)** | **PLANNED** |
| **20** | **M19** | **Public REST API — rate limiting, API key auth, OpenAPI docs** | **PLANNED** |
| **21** | **M12 (Phase 2)** | **Club logos/crests for 325+ teams** | **PLANNED** |
| **22** | **M18** | **xG integration research — data sourcing, Brier validation, ADR** | **PLANNED** |
| **23** | **M7** | **Two-leg tie analysis & modeling (research sprint)** | **PLANNED** |
| **24** | **M5** | **Bayesian parameter optimization — per-league tuning, cross-validation** | **PLANNED** |
| **25–26** | **M6** | **Full UEFA league expansion (data sourcing + frontend)** | **PLANNED** |
| **27** | **M4.5** | **Chart export (PNG/CSV), presets, shareable configs** | **PLANNED** |

---

## Dependencies Graph

```
M1 (Algorithm) ✅
 └──▶ M2 (Cross-League Calibration) ✅
       └──▶ M3 (Pipeline & Persistence) ✅
       │     ├──▶ M4 (Web Application) ✅
       │     │     ├── Sprint 6: Backend + API docs ✅
       │     │     ├── Sprint 7: Frontend + charts ✅
       │     │     └── Sprint 8: Predictions, Docker, CI/CD ✅
       │     │           ├──▶ M4.5 (Advanced Chart Features) [PARTIAL — Sprint 27]
       │     │           └──▶ M11 (UI Redesign — EloKit) ✅ [Sprints 12, 12.1]
       │     │                 └──▶ M12 (Flags & Logos) [Sprint 13 + TBD]
       │     │
       │     ├──▶ M15 (Per-Competition Elo Contribution) [Sprint 16]
       │     │
       │     ├──▶ M10 (Elo Calibration Fix) ✅ [Sprint 9]
       │     │
       │     ├──▶ M8 (Live Data & Fixtures) ✅
       │     │     ├── Sprint 9: Groundwork (ADR-004, fixtures/predictions tables) ✅
       │     │     └── Sprint 10: Persistence, API client, ingestion, fixtures page ✅
       │     │           └──▶ M9 (Prediction Tracking) [PARTIAL — 9b backfill in Sprint 14]
       │     │                 └──▶ M13 (Detailed Accuracy View) [Sprint 15]
       │     │
       │     └──▶ M5 (Advanced Parameter Optimization) [Sprint 18]
       │
       ├──▶ M6 (Full UEFA League Coverage) [Sprints 20-21]
       │     [depends on M2 + M3 + M4]
       │
       └──▶ M7 (Two-Leg Tie Modeling) [Sprint 19]
             [depends on M2]

M3 + M4 + M8 + M11 ──▶ M16 (Monte Carlo Season Simulation) [Sprint 18]
M3 + M4 + M11       ──▶ M17 (Upset Index) [Sprint 17]
M1 + M3             ──▶ M18 (xG Elo Updates) [Sprint 22 — research sprint]
M4 + M6             ──▶ M19 (Public REST API) [Sprint 20]
M3 + M4 + M11       ──▶ M20 (Head-to-Head Analysis) [Sprint 17]
M4 + M8 + M11       ──▶ M21 (Undervalued/Overvalued Metric) [Sprint 19]
```

## Architectural Decisions Tracker

| ADR | Milestone | Status | Document |
|-----|-----------|--------|----------|
| Storage engine | M3 | ✅ DECIDED | `docs/adr-storage-engine.md` — SQLite |
| Frontend tooling | M4 | ✅ DECIDED | `docs/adr-frontend-tooling.md` — Alpine.js + ApexCharts + Tailwind CSS |
| European cup data source | M2 | ✅ DECIDED | openfootball (CC0, 15 seasons CL) |
| Competition tier weight values | M2 | ✅ DECIDED (validated) | T1=1.5x, T2=1.2x, T3=1.2x, T4/T5=1.0x — Optuna confirmed optimal (Sprint 10) |
| Live data API source | M8 | ✅ DECIDED | `docs/adr-004-live-data-source.md` — football-data.org (free tier) |
| Initial rating calibration method | M10 | ✅ DECIDED | Warm-up period (2010-2016), implemented in Sprint 9 |
| Data persistence & migrations | M8 | ✅ DECIDED | Sprint 10 — DB as persistent state, numbered SQL migrations (`src/db/migrate.py`) |
| Tier weight optimization | M5 | ✅ DECIDED | Optuna Bayesian (150 trials): hand-picked defaults confirmed adequate (+0.015%) |
| Momentum metric for predictions | M14 | ✅ DECIDED (REJECTED) | Research 2026-03-19: adds −0.38% to 0.000% value; Elo already encodes form |
| Optimization framework | M5 | PENDING | Optuna / scikit-optimize / custom |
| Per-league vs. global parameters | M5 | PENDING | — |
| Full UEFA data source strategy | M6 | PENDING | — |
| Minimum data quality threshold | M6 | PENDING | — |
| Two-leg tie treatment | M7 | PENDING | Independent / aggregate / hybrid |
| Penalty shootout Elo impact | M7 | PENDING | — |
