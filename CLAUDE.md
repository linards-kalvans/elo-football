# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Elo rating system for European football clubs. The ultimate goal is a **web application** providing current and historical Elo ratings, plus match win-probability predictions.

The project has completed **Sprints 1-15.1** — a unified Elo engine rates 325 teams across 5 domestic leagues + CL/EL/Conference League (31,789 matches, with 2010-2016 warm-up period for calibration), with a fully documented FastAPI backend (17 endpoints, comprehensive API contract), unified "EloKit" frontend (single-page layout with context-aware routing, sidebar navigation, fixtures with Elo change deltas, Elo charts with team management, rankings with top-5 + context display, nation flag SVGs, competition logo badges), Docker/CI deployment infrastructure, live data integration via football-data.org API, automated prediction tracking with Brier score validation, 20,263 backfilled historical predictions with live/backfill source labeling, detailed prediction accuracy view with 3×3 Performance Grid, searchable Match Prediction Log, calibration chart, and Brier score trend visualization.

## Understanding the Code — CRITICAL

**ALWAYS use the CodeGraphContext MCP server FIRST when you need to:**
- Understand existing code structure or patterns
- Find where specific functionality is implemented
- Discover relationships between files, classes, or functions
- Search for code by name, pattern, or keyword
- Analyze code dependencies or call graphs

**Do not attempt to read files or search manually before using CodeGraphContext.** The MCP server provides indexed, relationship-aware code analysis that is far more efficient than manual file reading.

## Commands

```bash
uv sync                          # Install dependencies
uv run python <script>           # Run any script
uv run pytest tests/ -v          # Run tests (388 passing)
uv run uvicorn backend.main:app --reload  # Start FastAPI backend (port 8000)
cd data && bash fetch_league_csvs.sh  # Fetch raw match data (2010-2026)
uv run python scripts/run_daily_update.py  # Fetch live matches & fixtures
uv run python src/db/migrate.py  # Apply database migrations
```

## Project Structure

- **`src/`** — Core library: Elo engine, configuration, data ingestion, team name normalization
  - `elo_engine.py` — Core EloEngine class
  - `config.py` — EloSettings Pydantic model
  - `european_data.py` — CL/EL/Conference League parser
  - `team_names.py` — 100+ team name mappings
  - `data_loader.py` — Multi-league CSV loader
  - `db/` — SQLite database layer (schema, repository, validation, migrations)
  - `pipeline.py` — Idempotent data ingestion pipeline + incremental updates
  - `prediction.py` — Match prediction API
  - `live/` — Live data integration (football-data.org API client, team mapping, ingestion, prediction tracking)
- **`backend/`** — FastAPI web application (production-ready)
  - `main.py` — FastAPI app with 10+ REST endpoints, OpenAPI docs
  - `models.py` — Pydantic response models
  - `templates/` — Jinja2 templates (`base.html` layout + `index.html` unified page — replaces old multi-page templates)
  - `static/` — Frontend assets (Tailwind CDN, Alpine.js 3.13, ApexCharts 3.45, noUiSlider 15.7)
- **Deployment** — Docker + CI/CD
  - `Dockerfile` — Multi-stage build with uv
  - `docker-compose.yml` — App container with DB volume mount
  - `.github/workflows/ci.yml` — Lint → test → build pipeline
- **`data/`** — Raw match data (31,789 matches)
  - `epl/`, `laliga/`, `bundesliga/`, `seriea/`, `ligue1/` — Domestic league CSVs (Football-Data.co.uk, 2010-2026)
  - `europe/` — CL/EL/Conference League .txt files (openfootball)
  - `elo.db` — SQLite database (325 teams, 31,789 matches, 63K+ rating history records)
- **`scripts/`** — Operational scripts (daily update, DB backup, team mapping builder)
- **`tests/`** — Unit tests (pytest, 388 tests passing)
- **`docs/`** — Sprint plans, ADRs, milestones, API documentation
  - **`docs/api-contract.md`** — API contract documentation. **MUST be kept up to date** when endpoints are added, modified, or removed. Update response models, query parameters, and changelog.
- **`notebooks/`** — Analysis scripts, parameter sweeps, experiment outputs

## Architecture

- **`EloEngine`** (`src/elo_engine.py`): Stateless engine class. Takes `EloSettings`, exposes `compute_ratings(df)`, `get_rankings()`, `get_ratings_at()`. Supports tier-weighted K multipliers for European competition matches.
- **`EloSettings`** (`src/config.py`): Pydantic model with tunable parameters, configurable via `.env` (prefix `ELO_`). Includes tier weights (T1–T5) for competition-level K multipliers. `display_from_date` controls warm-up period boundary (default: 2016-08-01).
- **`european_data`** (`src/european_data.py`): Parser for openfootball .txt format. Loads CL/EL/Conference League data with stage classification and tier assignment.
- **`team_names`** (`src/team_names.py`): 100+ team name mappings from openfootball European names to Football-Data.co.uk domestic names.
- **`data_loader`** (`src/data_loader.py`): Multi-league loader for Football-Data.co.uk CSVs (5 domestic leagues).

## Key Concepts

- **Data sources**: Football-Data.co.uk (5 domestic leagues, 2010-2026) + openfootball (CL/EL/Conference League). Raw data under `data/`. Seasons 2010-2016 serve as warm-up period for calibration (hidden via `display_from_date`).
- **Data format**: Domestic dates DD/MM/YYYY, European dates parsed from openfootball text format. Match results encoded as H/D/A.
- **Elo features**: Home advantage, continuous time decay, promoted team initialization, margin-of-victory scaling (FiveThirtyEight formula), configurable logistic spread, competition tier weighting.
- **Competition tiers**: T1=CL knockout (1.5x K), T2=CL group/league (1.2x), T3=EL knockout (1.2x), T4=EL group/Conference (1.0x), T5=domestic (1.0x baseline).
- **Parameters**: All Elo parameters are env-configurable (`ELO_` prefix). Current defaults: K=20, HA=55, DR=0.90, PE=1400, SP=400.

## Known Issues / Tech Debt

- **Tier weight optimization**: Validated via Optuna — hand-picked defaults confirmed adequate (+0.015% improvement, not significant).
- **Two-leg tie modeling**: Knockout ties treated as independent matches (see M7 in milestones).

## Sprints & Roadmap

Sprint plans with detailed scope and status are in `docs/sprint-{N}-plan.md`. High-level roadmap in `docs/milestones.md`.

- Sprints 1–3: COMPLETED (algorithm, multi-league, parameter tuning)
- Sprint 4: COMPLETED (European data, cross-league calibration)
- Sprint 5: COMPLETED (data pipeline & persistence, SQLite database)
- Sprint 6: COMPLETED (FastAPI backend, API documentation)
- Sprint 7: COMPLETED (Frontend with ApexCharts + Alpine.js + noUiSlider)
- Sprint 8: COMPLETED (Prediction page, chart optimization, team stats API, Docker/CI, Pydantic fixes)
- Sprint 9: COMPLETED (Calibration fix, fixtures/predictions schema, live data ADR, test expansion)
  - ✅ Elo calibration: 2010-2016 warm-up period (31,789 matches, teams start at realistic ratings)
  - ✅ Database: fixtures + predictions tables with CRUD functions
  - ✅ API filtering by display_from_date (team history, peak/trough stats)
  - ✅ ADR-004: football-data.org selected for live data (Sprint 10)
  - ✅ 237 tests passing (was 164)
- Sprint 10: COMPLETED (Live API integration via football-data.org, tier weight optimization, fixtures frontend, prediction tracking)
  - ✅ Schema migration system (4 migrations), incremental update pipeline, DB backup script
  - ✅ football-data.org async API client with rate limiting and retries
  - ✅ Team name mapping (150+ known + fuzzy fallback), live ingestion pipeline
  - ✅ Fixtures page with Elo prediction bars, `/api/prediction-accuracy` endpoint
  - ✅ Tier weight optimization: Optuna confirmed hand-picked defaults are optimal
  - ✅ 363 tests passing (was 237)
- Sprint 11: COMPLETED (Dockerized daily update cron, prediction history + accuracy frontend)
- Sprint 12: COMPLETED (EloKit UI redesign — unified single-page layout, sidebar navigation, context-aware routing)
  - ✅ Single `index.html` replaces 8 templates; URL scheme `/{nation}/{league}/{team}`
  - ✅ Context-aware API endpoints: `/api/fixtures/scoped`, `/api/chart/scoped`, `/api/accuracy/scoped`, `/api/sidebar`
  - ✅ Sidebar with nations/leagues/cups, breadcrumb navigation, EloKit branding
  - ✅ Old templates retired, old routes redirect
- Sprint 12.1: COMPLETED (EloKit polish — data loading regression fix, fixtures pagination, chart controls, rankings display)
- Sprint 13: COMPLETED (Nation flags & competition logos — SVG flags, competition badge logos, API URL fields, frontend integration)
  - ✅ Fixed nested `<button>` and `x-data` scope issues causing data loading regression
  - ✅ Fixtures: 3+3 default with "Load more..." offset-based pagination
  - ✅ Chart: team add/remove via `chart.updateOptions()`, zoom controls
  - ✅ Rankings: top 5 + team ±3 context with "View all" toggle
  - ✅ 360 tests passing
- Sprint 13: COMPLETED (Nation flags & competition logos)
  - ✅ 6 country flag SVGs from flag-icons (MIT), 8 competition badge SVGs
  - ✅ API: `flag_url` on SidebarNation, `logo_url` on SidebarCompetition, `competition_logo_url` on ScopedFixtureEntry
  - ✅ Sidebar: real flag images replace emoji, competition logos replace generic icons
  - ✅ Breadcrumbs: flag image next to country name
  - ✅ Fixtures: competition logo from API with `competitionIcon()` fallback
  - ✅ `flagEmoji()` function removed
  - ✅ 364 tests passing
- Sprint 14: COMPLETED (Prediction pipeline fix & historical backfill)
  - ✅ Fixed prediction scoring: `score_completed_matches()` now called in daily update, fixture status transitions to `completed`
  - ✅ HTTP 403 retry: 3 attempts with 10s/60s/120s delays (401 still immediate failure)
  - ✅ Historical backfill: 20,263 predictions with pre-match Elo ratings, mean Brier score 0.586
  - ✅ Schema migration 005: `source` column on predictions table (`live` vs `backfill`)
  - ✅ Frontend: by-source breakdown in accuracy dashboard, source labels in prediction history
  - ✅ Fixed accuracy detail view `by_competition` dict→array transformation
  - ✅ 364 tests passing
- Sprint 15: COMPLETED (Detailed prediction accuracy view)
  - ✅ Prediction Performance Grid: 3×3 confusion matrix (predicted vs actual outcome) with heatmap styling
  - ✅ Match Prediction Log: paginated, searchable table with multi-word team search, probability bars, Brier coloring
  - ✅ New endpoint: `GET /api/accuracy/grid` with country/competition/team_id/source scoping
  - ✅ Extended `/api/prediction-accuracy` and `/api/prediction-history` with country + team_id filters
  - ✅ "View details" navigation from compact accuracy widget to full detail panel
  - ✅ Context-aware: all detail views respect current navigation scope (global/nation/league/team)
  - ✅ 388 tests passing (was 364)
- Sprint 15.1: COMPLETED (Accuracy charts, Elo deltas & polish)
  - ✅ Calibration chart: 10-bucket bar chart with perfect-calibration reference line (ApexCharts)
  - ✅ Brier score trend chart: rolling area chart with mean reference and zoom
  - ✅ Elo change on completed fixtures: color-coded +N/-N deltas from ratings_history
  - ✅ Logo & breadcrumb polish: increased sizes, competition logos in breadcrumbs
  - ✅ API contract doc updated: 17 endpoints documented (was 7)
  - ✅ 388 tests passing (no regressions)

## Roles

The project uses specialized Claude Code skills (defined in `.claude/commands/`):

- **`/manager`** — Project coordination, sprint planning, scope management
- **`/analyst`** — Elo algorithm design, parameter tuning, model validation
- **`/fullstack`** — FastAPI backend, frontend (Alpine.js + ApexCharts + Tailwind), full-stack features
- **`/data-eng`** — Data pipelines, ingestion, schema design, database architecture
- **`/devops`** — Docker, CI/CD, deployment, infrastructure
- **`/tech-writer`** — Docstrings, API documentation, inline comments
- **`/test-runner`** — Run tests, interpret results, report failures
