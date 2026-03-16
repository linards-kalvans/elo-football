# Milestone Plan

> Last updated: 2026-03-15

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

**Sprints:** TBD | **Status:** PARTIALLY COMPLETE

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

**Sprints:** TBD | **Status:** NOT STARTED

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

**Sprints:** TBD | **Status:** NOT STARTED

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

**Sprints:** TBD | **Status:** NOT STARTED

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

**Sprints:** [10](sprint-10-plan.md)–11 | **Status:** IN PROGRESS | **Priority:** HIGH

Transition from historical-only data to quasi-live updates with upcoming fixtures and completed match results.

**Groundwork completed (Sprint 9):**
- ADR-004: football-data.org selected as live data source (`docs/adr-004-live-data-source.md`)
- Database schema: fixtures & predictions tables with CRUD functions
- 2010-2016 warm-up period for calibration (display_from_date filtering)

**Remaining scope:**

### 8a. Data Persistence & Deployment Strategy (Sprint 10, prerequisite)
- **DB as persistent state**: Remove `elo.db` from git, treat as volume-mounted persistent data
- **Schema migrations**: Numbered migration system so schema changes apply without data loss
- **Seed vs. incremental separation**: `run_pipeline()` for cold-start only; incremental ingestion thereafter
- **DB backup on deploy**: Snapshot database before each deployment for rollback
- **Incremental ratings**: Avoid full `DELETE FROM ratings_history` recompute on every update

### 8b. Data Source Integration (Sprint 10)
- **football-data.org API client**: Async client with rate limiting (10 calls/min), auth, error handling
- **Team ID mapping**: Map API team IDs to existing 325 teams
- **Recent results API**: Fetch completed match results for rating updates
- **Data freshness policy**: 2x daily scheduled fetch (6am, 6pm)

### 8c. Pipeline Automation (Sprint 10-11)
- **Scheduled fetch**: systemd timer or cron for automated ingestion
- **Incremental rating updates**: Only recompute ratings for new matches, not full history
- **Match result validation**: Confirm match is final (not abandoned, not postponed)

### 8d. Fixtures Frontend (Sprint 10-11)
- **Fixtures page**: Upcoming matches with pre-match Elo predictions
- **Grouped by competition**: Sorted by date, linked to team pages

**Exit criteria:**
- [ ] Database survives deployments without data loss
- [ ] Schema migrations apply cleanly on existing databases
- [ ] Upcoming fixtures fetched and displayed in frontend
- [ ] Completed matches auto-ingested within 24 hours
- [ ] Ratings updated automatically after new results
- [ ] API rate limits and costs acceptable for production

---

## M9: Prediction Tracking & Validation

**Sprints:** TBD (11+) | **Status:** PARTIALLY COMPLETE | **Priority:** MEDIUM

Track predictions made by the system and compare them to actual outcomes, enabling performance monitoring and user transparency.

**Completed (Sprint 9):**
- Predictions table with CRUD functions (insert_prediction, get_predictions_for_fixture)
- CHECK constraint ensuring exactly one of match_id/fixture_id is set

**Remaining scope:**

### 9a. Prediction Automation
- Auto-insert predictions for upcoming fixtures when fetched
- After match completes: compare prediction vs result, compute Brier score
- Prediction versioning if match rescheduled

### 9b. Performance Metrics
- **Accuracy tracking**: Log-loss, Brier score, accuracy over rolling windows
- **Calibration curves**: Are 60% predictions actually 60% accurate?
- **Dashboard**: Show model performance over time (last week, month, season)
- **Alerts**: Flag if model performance degrades below threshold

### 9c. User-Facing Features
- **Prediction history page**: "Here's what we predicted for last weekend's matches"
- **Accuracy badge**: Display model's recent accuracy on prediction widget
- **Confidence intervals**: Show uncertainty around predictions

**Depends on:** M8 (live data for actual outcomes), M4 (frontend to display)

**Exit criteria:**
- [ ] All predictions stored in database before matches
- [ ] Prediction accuracy dashboard live
- [ ] Users can view prediction history and outcomes
- [ ] Brier score and log-loss tracked over time

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

## M11: UI Redesign

**Sprints:** TBD (12) | **Status:** NOT STARTED | **Priority:** MEDIUM

Redesign the frontend based on user-provided mock designs. May require new features and components depending on the design vision.

**Scope:**
- Implement UI from provided mock designs (Figma, screenshots, or similar)
- Visual identity refresh (colors, typography, layout, spacing)
- Improved mobile experience and responsive design
- New pages or components as required by the designs
- Potential new features driven by the redesign (TBD based on mocks)

**Depends on:** M4 (current web app as baseline), mock designs provided by stakeholder

**Key questions (to resolve when mocks are provided):**
- Does the redesign require new API endpoints or data?
- Are there new pages/features beyond restyling existing ones?
- Should we adopt a component library or design system?
- Does the redesign affect the tech stack (e.g., move from Tailwind CDN to built CSS)?

**Exit criteria:**
- [ ] All pages match provided mock designs
- [ ] Responsive on mobile, tablet, and desktop
- [ ] Any new features required by the designs are functional
- [ ] Existing functionality preserved (no regressions)
- [ ] Accessibility basics (contrast, keyboard nav, semantic HTML)

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
| **10** | **M8** | **Data persistence strategy, live API client, ingestion pipeline, fixtures page** | **PLANNED** |
| **11** | **M8, M9** | **Prediction tracking, accuracy dashboard, scheduled automation** | **PLANNED** |
| **12** | **M11** | **UI redesign from mock designs** | **PLANNED** |
| **13** | **M4.5** | **Chart export (PNG/CSV), presets, shareable configs** | **PLANNED** |
| **14** | **M5** | **Bayesian parameter optimization (Optuna), tier weight sweep** | **PLANNED** |
| **15** | **M7** | **Two-leg tie analysis & modeling** | **PLANNED** |
| **16–17** | **M6** | **Full UEFA league expansion (data sourcing + frontend)** | **PLANNED** |

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
       │     │           ├──▶ M4.5 (Advanced Chart Features) [PARTIAL]
       │     │           └──▶ M11 (UI Redesign) [PLANNED]
       │     │
       │     ├──▶ M10 (Elo Calibration Fix) ✅ [Sprint 9]
       │     │
       │     ├──▶ M8 (Live Data & Fixtures) [IN PROGRESS]
       │     │     ├── Sprint 9: Groundwork (ADR-004, fixtures/predictions tables) ✅
       │     │     ├── Sprint 10: Persistence, API client, ingestion [PLANNED]
       │     │     └── Sprint 11: Automation, fixtures frontend [PLANNED]
       │     │           └──▶ M9 (Prediction Tracking) [PARTIAL → Sprint 11]
       │     │
       │     └──▶ M5 (Advanced Parameter Optimization) [Sprint 14]
       │
       ├──▶ M6 (Full UEFA League Coverage) [Sprints 16-17]
       │     [depends on M2 + M3 + M4]
       │
       └──▶ M7 (Two-Leg Tie Modeling) [Sprint 15]
             [depends on M2]
```

## Architectural Decisions Tracker

| ADR | Milestone | Status | Document |
|-----|-----------|--------|----------|
| Storage engine | M3 | ✅ DECIDED | `docs/adr-storage-engine.md` — SQLite |
| Frontend tooling | M4 | ✅ DECIDED | `docs/adr-frontend-tooling.md` — Alpine.js + ApexCharts + Tailwind CSS |
| European cup data source | M2 | ✅ DECIDED | openfootball (CC0, 15 seasons CL) |
| Competition tier weight values | M2 | ⚠️ DECIDED (needs optimization) | T1=1.5x, T2=1.2x, T3=1.2x, T4/T5=1.0x (hand-picked) |
| Live data API source | M8 | ✅ DECIDED | `docs/adr-004-live-data-source.md` — football-data.org (free tier) |
| Initial rating calibration method | M10 | ✅ DECIDED | Warm-up period (2010-2016), implemented in Sprint 9 |
| **Data persistence & migrations** | **M8** | **PENDING** | **Sprint 10 Task 0 — DB as persistent state, migration system** |
| Optimization framework | M5 | PENDING | Optuna / scikit-optimize / custom |
| Per-league vs. global parameters | M5 | PENDING | — |
| Full UEFA data source strategy | M6 | PENDING | — |
| Minimum data quality threshold | M6 | PENDING | — |
| Two-leg tie treatment | M7 | PENDING | Independent / aggregate / hybrid |
| Penalty shootout Elo impact | M7 | PENDING | — |
