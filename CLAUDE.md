# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Elo rating system for European football clubs. The ultimate goal is a **web application** providing current and historical Elo ratings, plus match win-probability predictions.

The project has completed **Sprints 1-6** — a unified Elo engine rates 300 teams across 5 domestic leagues + CL/EL/Conference League (20,833 matches), with a fully documented FastAPI backend providing REST API access to all data. Next: Frontend implementation (Sprint 7).

## Understanding the code
To read / understand the code, always use the CodeGraphContext MCP server first.

## Commands

```bash
uv sync                          # Install dependencies
uv run python <script>           # Run any script
uv run pytest tests/ -v          # Run tests (153 passing)
uv run uvicorn backend.main:app --reload  # Start FastAPI backend (port 8000)
cd data && bash fetch_epl_csvs.sh  # Fetch raw match data
```

## Project Structure

- **`src/`** — Core library: Elo engine, configuration, data ingestion, team name normalization
- **`notebooks/`** — Analysis scripts, parameter sweeps, outputs
- **`tests/`** — Unit tests (pytest, 153 tests)
- **`data/`** — Raw match CSVs (Football-Data.co.uk) + European data (openfootball .txt files)
- **`docs/`** — Sprint plans, experiment logs, project spec
- **`backend/`** — FastAPI REST API (8 endpoints, OpenAPI docs)
  - `templates/` — Jinja2 templates for frontend pages
  - `static/` — CSS, JS, images (Tailwind CDN, HTMX, Alpine.js, Chart.js)

## Architecture

- **`EloEngine`** (`src/elo_engine.py`): Stateless engine class. Takes `EloSettings`, exposes `compute_ratings(df)`, `get_rankings()`, `get_ratings_at()`. Supports tier-weighted K multipliers for European competition matches.
- **`EloSettings`** (`src/config.py`): Pydantic model with tunable parameters, configurable via `.env` (prefix `ELO_`). Includes tier weights (T1–T5) for competition-level K multipliers.
- **`european_data`** (`src/european_data.py`): Parser for openfootball .txt format. Loads CL/EL/Conference League data with stage classification and tier assignment.
- **`team_names`** (`src/team_names.py`): 100+ team name mappings from openfootball European names to Football-Data.co.uk domestic names.
- **`data_loader`** (`src/data_loader.py`): Multi-league loader for Football-Data.co.uk CSVs (5 domestic leagues).

## Key Concepts

- **Data sources**: Football-Data.co.uk (5 domestic leagues) + openfootball (CL/EL/Conference League). Raw data under `data/`. Additional data required for quasi-live data.
- **Data format**: Domestic dates DD/MM/YYYY, European dates parsed from openfootball text format. Match results encoded as H/D/A.
- **Elo features**: Home advantage, continuous time decay, promoted team initialization, margin-of-victory scaling (FiveThirtyEight formula), configurable logistic spread, competition tier weighting.
- **Competition tiers**: T1=CL knockout (1.5x K), T2=CL group/league (1.2x), T3=EL knockout (1.2x), T4=EL group/Conference (1.0x), T5=domestic (1.0x baseline).
- **Parameters**: All Elo parameters are env-configurable (`ELO_` prefix). Current defaults: K=20, HA=55, DR=0.90, PE=1400, SP=400.

## Known Issues / Tech Debt

- **Tier weight optimization**: Current tier weights are hand-picked, not optimized via sweep.
- **Two-leg tie modeling**: Knockout ties treated as independent matches (see M7 in milestones).
- **Chart.js advanced features**: Current implementation uses basic charts; future enhancements include zoom/pan, multi-team overlay, date range selection.
- **Pydantic deprecation warnings**: 54 warnings in backend/models.py (tracked in Sprint 8).

## Sprints & Roadmap

Sprint plans with detailed scope and status are in `docs/sprint-{N}-plan.md`. High-level roadmap in `docs/milestones.md`.

- Sprints 1–3: COMPLETED (algorithm, multi-league, parameter tuning)
- Sprint 4: COMPLETED (European data, cross-league calibration)
- Sprint 5: COMPLETED (data pipeline & persistence, SQLite database)
- Sprint 6: COMPLETED (FastAPI backend, API documentation)
- Sprint 7: IN PROGRESS (Frontend with HTMX + Alpine.js + Chart.js, deployment to Hetzner VPS)
- Sprint 8: PLANNED (Technical debt: Pydantic warnings, tier weight optimization, test coverage)

## Roles

The project uses specialized Claude Code skills (defined in `.claude/commands/`):

- **`/manager`** — Project coordination, sprint planning, scope management
- **`/analyst`** — Elo algorithm design, parameter tuning, model validation
- **`/backend`** - Backend Python engineer, API
- **`/data-eng`** — Data pipelines, ingestion, schema design
- **`/devops`** — Testing, CI, frontend, deployment
