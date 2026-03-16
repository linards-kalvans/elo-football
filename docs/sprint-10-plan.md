# Sprint 10 Plan — Data Persistence & Live API Integration

> Status: COMPLETED (2026-03-16)
> Depends on: Sprint 9 (completed)

## Goals

1. **Data persistence strategy** — Make the database a durable, deployment-surviving asset with schema migrations (prerequisite for everything else)
2. **Live data integration** — Connect to football-data.org API (ADR-004) for automated match ingestion
3. **Tier weight optimization** — Replace hand-picked tier weights with data-driven values (Optuna/Bayesian)
4. **Fixtures frontend** — Display upcoming matches with pre-match Elo predictions

## Tasks

### Task 0: Data Persistence & Deployment Strategy (PREREQUISITE) ✅
**Role:** `/devops` + `/data-eng` | **Effort:** ~8h | **Priority:** P0

**Problem:** Currently the database is rebuilt from CSVs on each deployment. With live data, this loses all API-ingested matches. The gap between "latest CSV" and "today" widens over time.

**Deliverables:**

#### 0a. Remove elo.db from git
- Add `data/elo.db` and `data/elo.db-wal` and `data/elo.db-shm` to `.gitignore`
- Remove from git tracking (`git rm --cached`)
- Document that the DB is persistent state, not a build artifact

#### 0b. Schema migration system
- Create `src/db/migrations/` directory with numbered SQL migration files
- Migration runner: tracks applied migrations in a `schema_migrations` table
- Each migration is an idempotent SQL file (e.g., `001_initial_schema.sql`, `002_add_fixtures.sql`)
- Runner applies pending migrations on app startup
- Existing schema.sql becomes migration 001

#### 0c. Separate seed from incremental ingestion
- `run_pipeline()` remains for cold-start (fresh DB from CSVs) — only used for initial deployment or disaster recovery
- New `run_incremental_update()` function: accepts new matches, appends to DB, recomputes only affected ratings
- Deploy step should run migrations only, NOT re-run full pipeline
- Pipeline currently does `DELETE FROM ratings_history` on every run — this must only happen on full seed, never on incremental

#### 0d. DB backup on deploy
- Pre-deploy script: `cp data/elo.db data/backups/elo-$(date +%Y%m%d-%H%M%S).db`
- Retain last 5 backups, prune older ones
- CI/CD deploy step calls backup before `docker compose up`

#### 0e. Update CI/CD pipeline
- Test job: create ephemeral DB from pipeline (no change — tests use fresh DB)
- Deploy job: backup existing DB → pull code → run migrations → restart container
- Remove any step that would overwrite the production database
- Health check after deploy

**Exit criteria:**
- [x] `elo.db` not tracked in git
- [x] Migration system applies schema changes without data loss
- [x] Deploy does NOT re-run full pipeline or overwrite DB
- [x] Pre-deploy backup is automated
- [x] Existing data survives a redeployment

---

### Task 1: football-data.org API Client ✅
**Role:** `/data-eng` | **Effort:** ~6h | **Priority:** P1

- Create `src/live/football_data_client.py` with async API client
- Implement rate limiting (10 calls/min), exponential backoff, error handling
- Support endpoints: `/competitions/{id}/matches`, `/teams/{id}`
- Auth via `FOOTBALL_DATA_API_KEY` env var
- Map API competition codes to internal competition IDs (PL, PD, BL1, SA, FL1, CL, EL, EC)

### Task 2: Team ID Mapping ✅
**Role:** `/data-eng` | **Effort:** ~4h | **Priority:** P1

- Create `api_team_mappings` table (api_source, api_team_id → team_id)
- Build one-time mapping script matching football-data.org team IDs to existing 325 teams
- Handle name variations between API and Football-Data.co.uk naming
- Schema migration for the new table (uses Task 0b migration system)

### Task 3: Live Ingestion Pipeline ✅
**Role:** `/data-eng` | **Effort:** ~6h | **Priority:** P1

- Create `src/live/ingestion.py` — fetch recent matches, upsert into matches table
- Fetch upcoming fixtures, upsert into fixtures table
- Use `run_incremental_update()` from Task 0c (not full pipeline recompute)
- Scheduled execution: systemd timer or cron (2x daily: 6am, 6pm)

### Task 4: Fixtures Frontend Page ✅
**Role:** `/fullstack` | **Effort:** ~4h | **Priority:** P2

- Create `/fixtures` page showing upcoming matches from fixtures table
- Show pre-match Elo predictions (auto-generated via prediction module)
- Group by competition, sorted by date
- Link to team pages

### Task 5: Tier Weight Optimization ✅
**Role:** `/analyst` | **Effort:** ~8h | **Priority:** P2

- Use Optuna for Bayesian optimization of tier weights (T1-T5)
- Objective: maximize log-likelihood of match outcomes
- Cross-validation on held-out seasons
- **Result:** Only +0.015% improvement over hand-picked defaults — no change to defaults needed

### Task 6: Prediction Tracking ✅
**Role:** `/data-eng` | **Effort:** ~3h | **Priority:** P3

- Auto-insert predictions for upcoming fixtures
- After match completes: compare prediction vs result, compute Brier score
- API endpoint: `/api/prediction-accuracy` with aggregate stats

## Task Dependencies

```
Task 0 (Persistence) ──▶ Task 1 (API Client) ──▶ Task 3 (Live Ingestion)
                     ──▶ Task 2 (Team Mapping) ──▶ Task 3
                                                     └──▶ Task 4 (Fixtures Frontend)
                                                     └──▶ Task 6 (Prediction Tracking)

Task 5 (Tier Optimization) — independent, can run in parallel
```

## Out of Scope

- Prediction tracking frontend (Sprint 11)
- Real-time WebSocket updates
- Expanding to additional leagues beyond current 8
- UI redesign (Sprint 12)

## Results

**Completed:** 2026-03-16 | **Tests:** 363 passing (up from 237) | **0 warnings**

### Key Deliverables
- **Schema migration system** (`src/db/migrate.py`) — numbered SQL migrations tracked in `schema_migrations` table, 4 migrations (001–004)
- **Incremental update pipeline** (`run_incremental_update()` in `src/pipeline.py`) — append-only match ingestion with full rating recompute
- **DB backup script** (`scripts/backup_db.sh`) — WAL-safe backup with 5-copy rotation
- **CI/CD updated** — deploy step: backup → migrate → incremental update → health check
- **Async API client** (`src/live/football_data_client.py`) — token-bucket rate limiter (10 req/min), exponential backoff, 3 retries
- **Team name mapping** (`src/live/team_mapping.py`) — 150+ known mappings + fuzzy matching fallback
- **Live ingestion** (`src/live/ingestion.py`) — `fetch_and_ingest_matches()`, `fetch_and_ingest_fixtures()`, `run_daily_update()`
- **Fixtures page** (`/fixtures`) — Alpine.js frontend with competition filters and prediction probability bars
- **Prediction tracker** (`src/live/prediction_tracker.py`) — Brier score computation, `/api/prediction-accuracy` endpoint
- **Tier optimization** — Optuna Bayesian optimization (150 trials): hand-picked defaults confirmed adequate (+0.015%)

### New Files
- `src/live/__init__.py`, `football_data_client.py`, `team_mapping.py`, `ingestion.py`, `prediction_tracker.py`
- `src/db/migrate.py`, `src/db/migrations/001–004_*.sql`
- `scripts/backup_db.sh`, `scripts/run_daily_update.py`, `scripts/build_team_mappings.py`
- `backend/templates/fixtures.html`
- `notebooks/tier_optimization.py`
- `tests/test_football_data_client.py`, `test_team_mapping.py`, `test_ingestion.py`, `test_prediction_tracker.py`

### Bug Fixes (post-implementation)
- **429 rate limit cascade**: Reduced initial burst tokens from 10→3, added 6.5s minimum inter-request delay
- **TypeError on None team names**: Added guards for TBD teams in CL knockout fixtures from API
- **EloSettings crash with .env**: Added `extra="ignore"` to Pydantic SettingsConfigDict

### Activation Steps
1. `git rm --cached data/elo.db` (one-time)
2. `uv run python scripts/build_team_mappings.py` (populate API team mappings)
3. `uv run python scripts/run_daily_update.py` (fetch matches and fixtures)
4. Set up cron: `0 6,18 * * * cd /path/to/elo-football && uv run python scripts/run_daily_update.py`
