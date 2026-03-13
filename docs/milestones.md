# Milestone Plan

> Last updated: 2026-03-13

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
- Database schema with 5 tables: teams, competitions, matches, ratings_history, parameters
- Automated fetch → ingest → rate → persist pipeline (idempotent, logged)
- Match prediction Python API (`predict_match()`, `predict_match_from_db()`)
- Data validation and monitoring (schema drift, completeness, duplicates)

**Key results:**
- SQLite database at `data/elo.db` with WAL mode and foreign keys
- `src/db/` module: connection, schema, repository, seed, validation
- `src/pipeline.py`: idempotent pipeline with duplicate detection
- `src/prediction.py`: match prediction API with database integration
- Comprehensive test coverage (89 tests passing)

**Exit criteria:**
- [x] Storage engine ADR written and decision made
- [x] Database populated with all historical data
- [x] Pipeline runs end-to-end and is schedulable
- [x] Prediction API returns calibrated probabilities

---

## M4: Web Application

**Sprints:** [6](sprint-6-plan.md)–[7](sprint-7-plan.md) | **Status:** IN PROGRESS

Ship the user-facing web application — the project's ultimate deliverable.

**Key deliverables:**
- **Frontend tooling ADR** (`docs/adr-frontend-tooling.md`) — HTMX + Alpine.js + Chart.js + Tailwind CSS ✅
- FastAPI backend with rankings, team detail, prediction, and search endpoints ✅
- **Comprehensive API documentation** — contract doc, example responses, OpenAPI spec ✅
- Interactive frontend: rankings table, Elo trajectory charts, team detail pages (IN PROGRESS)
- Match prediction widget (select two teams → win/draw/loss probabilities)
- Historical date explorer (date picker → ratings at any past date)
- Deployment: Docker, CI/CD to Hetzner VPS

**Key decisions:**
- Frontend tooling: HTMX + Alpine.js + Chart.js (Sprint 6 ADR) ✅
- Frontend structure: backend/templates/ + backend/static/ (co-located with FastAPI) ✅
- Hosting: Hetzner VPS with Docker container ✅
- Deployment: GitHub Actions CI/CD ✅
- Chart.js scope: Start simple (basic line charts), defer advanced features (zoom/pan, multi-team overlay) to future enhancement

| Sprint | Focus | Status |
|--------|-------|--------|
| [Sprint 6](sprint-6-plan.md) | Frontend ADR, FastAPI backend, API documentation, database integration | COMPLETED ✅ |
| [Sprint 7](sprint-7-plan.md) | Frontend (rankings, team detail, charts), predictions, historical explorer, deployment | IN PROGRESS 🚧 |

**Exit criteria:**
- [ ] Web app deployed to Hetzner VPS and publicly accessible
- [ ] Rankings, team detail, predictions, and historical queries all working
- [x] API fully documented with contract doc and example responses
- [ ] Responsive on mobile and desktop
- [ ] CI/CD pipeline: lint → test → build → deploy

---

## M4.5: Chart.js Enhancements

**Sprints:** TBD | **Status:** NOT STARTED

Enhance the Chart.js visualizations with advanced interactive features deferred from Sprint 7.

**Scope:**
- **Zoom and pan**: Allow users to zoom into specific time periods and pan across the full timeline
- **Multi-team overlay**: Compare multiple teams on a single chart (different colored lines)
- **Date range selection**: Interactive date range picker to filter chart data
- **Export functionality**: Download chart as PNG or CSV
- **Performance optimization**: Lazy loading for teams with >1000 matches

**Depends on:** M4 (Sprint 7 frontend complete)

**Key questions:**
- Use Chart.js zoom plugin or custom implementation?
- How many teams can overlay before performance degrades?
- Should we add chart presets (e.g., "Last season", "All time", "CL campaigns only")?

**Exit criteria:**
- [ ] Zoom/pan working smoothly on desktop and mobile
- [ ] Multi-team overlay supports at least 5 teams simultaneously
- [ ] Date range picker integrated with chart updates
- [ ] Chart performance acceptable with 2000+ data points

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

## Dependencies Graph

```
M1 (Algorithm)
 └──▶ M2 (Cross-League Calibration)
       └──▶ M3 (Pipeline & Persistence)
       │     └──▶ M4 (Web Application)
       │           ├── Sprint 6: Backend + Frontend Foundation
       │           └── Sprint 7: Predictions, History, Deploy
       │
       ├──▶ M5 (Advanced Parameter Optimization)
       │     [depends on M1 + M3]
       │
       ├──▶ M6 (Full UEFA League Coverage)
       │     [depends on M2 + M3 + M4]
       │
       └──▶ M7 (Two-Leg Tie Modeling)
             [depends on M2]
```

## Architectural Decisions Tracker

| ADR | Milestone | Status | Document |
|-----|-----------|--------|----------|
| Storage engine (SQLite / Postgres / DuckDB / Parquet) | M3 | PENDING | `docs/adr-storage-engine.md` |
| Frontend tooling (HTMX / Alpine / SPA / charting lib) | M4 | PENDING | `docs/adr-frontend-tooling.md` |
| European cup data source | M2 | DECIDED | openfootball (CC0, 15 seasons CL) |
| Competition tier weight values | M2 | DECIDED | T1=1.5x, T2=1.2x, T3=1.2x, T4/T5=1.0x |
| Optimization framework (Optuna / scikit-optimize / custom) | M5 | PENDING | — |
| Per-league vs. global parameters | M5 | PENDING | — |
| Full UEFA data source strategy | M6 | PENDING | — |
| Minimum data quality threshold for league inclusion | M6 | PENDING | — |
| Two-leg tie treatment (independent / aggregate / hybrid) | M7 | PENDING | — |
| Penalty shootout Elo impact | M7 | PENDING | — |
