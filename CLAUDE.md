# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Elo rating system for European football clubs. The ultimate goal is a **web application** providing current and historical Elo ratings, plus match win-probability predictions.

The project has completed **Sprints 1-9** — a unified Elo engine rates 325 teams across 5 domestic leagues + CL/EL/Conference League (31,789 matches, with 2010-2016 warm-up period for calibration), with a fully documented FastAPI backend, interactive frontend (rankings, team profiles with stats, comparison charts, match predictions), Docker/CI deployment infrastructure, and database schema ready for live data integration. Next: Sprint 10 (live API integration via football-data.org, tier weight optimization).

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
uv run pytest tests/ -v          # Run tests (237 passing)
uv run uvicorn backend.main:app --reload  # Start FastAPI backend (port 8000)
cd data && bash fetch_league_csvs.sh  # Fetch raw match data (2010-2026)
```

## Project Structure

- **`src/`** — Core library: Elo engine, configuration, data ingestion, team name normalization
  - `elo_engine.py` — Core EloEngine class
  - `config.py` — EloSettings Pydantic model
  - `european_data.py` — CL/EL/Conference League parser
  - `team_names.py` — 100+ team name mappings
  - `data_loader.py` — Multi-league CSV loader
  - `db/` — SQLite database layer (schema, repository, validation)
  - `pipeline.py` — Idempotent data ingestion pipeline
  - `prediction.py` — Match prediction API
- **`backend/`** — FastAPI web application (production-ready)
  - `main.py` — FastAPI app with 10+ REST endpoints, OpenAPI docs
  - `models.py` — Pydantic response models
  - `templates/` — Jinja2 templates (rankings.html, team.html, compare.html, predict.html, base.html)
  - `static/` — Frontend assets (Tailwind CDN, Alpine.js 3.13, ApexCharts 3.45, noUiSlider 15.7)
- **Deployment** — Docker + CI/CD
  - `Dockerfile` — Multi-stage build with uv
  - `docker-compose.yml` — App container with DB volume mount
  - `.github/workflows/ci.yml` — Lint → test → build pipeline
- **`data/`** — Raw match data (31,789 matches)
  - `epl/`, `laliga/`, `bundesliga/`, `seriea/`, `ligue1/` — Domestic league CSVs (Football-Data.co.uk, 2010-2026)
  - `europe/` — CL/EL/Conference League .txt files (openfootball)
  - `elo.db` — SQLite database (325 teams, 31,789 matches, 63K+ rating history records)
- **`tests/`** — Unit tests (pytest, 237 tests passing)
- **`docs/`** — Sprint plans, ADRs, milestones, API documentation
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

- **Tier weight optimization**: Current tier weights are hand-picked, not optimized via sweep (Sprint 10+).
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
- Sprint 10: PLANNED (Live API integration via football-data.org, tier weight optimization, fixtures frontend)

## Roles

The project uses specialized Claude Code skills (defined in `.claude/commands/`):

- **`/manager`** — Project coordination, sprint planning, scope management
- **`/analyst`** — Elo algorithm design, parameter tuning, model validation
- **`/fullstack`** — FastAPI backend, frontend (Alpine.js + ApexCharts + Tailwind), full-stack features
- **`/data-eng`** — Data pipelines, ingestion, schema design, database architecture
- **`/devops`** — Docker, CI/CD, deployment, infrastructure
- **`/tech-writer`** — Docstrings, API documentation, inline comments
- **`/test-runner`** — Run tests, interpret results, report failures
