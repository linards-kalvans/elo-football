# Sprint 10 Plan — Data Persistence & Live API Integration

> Status: PLANNED
> Depends on: Sprint 9 (completed)

## Goals

1. **Data persistence strategy** — Make the database a durable, deployment-surviving asset with schema migrations (prerequisite for everything else)
2. **Live data integration** — Connect to football-data.org API (ADR-004) for automated match ingestion
3. **Tier weight optimization** — Replace hand-picked tier weights with data-driven values (Optuna/Bayesian)
4. **Fixtures frontend** — Display upcoming matches with pre-match Elo predictions

## Tasks

### Task 0: Data Persistence & Deployment Strategy (PREREQUISITE)
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
- [ ] `elo.db` not tracked in git
- [ ] Migration system applies schema changes without data loss
- [ ] Deploy does NOT re-run full pipeline or overwrite DB
- [ ] Pre-deploy backup is automated
- [ ] Existing data survives a redeployment

---

### Task 1: football-data.org API Client
**Role:** `/data-eng` | **Effort:** ~6h | **Priority:** P1

- Create `src/live/football_data_client.py` with async API client
- Implement rate limiting (10 calls/min), exponential backoff, error handling
- Support endpoints: `/competitions/{id}/matches`, `/teams/{id}`
- Auth via `FOOTBALL_DATA_API_KEY` env var
- Map API competition codes to internal competition IDs (PL, PD, BL1, SA, FL1, CL, EL, EC)

### Task 2: Team ID Mapping
**Role:** `/data-eng` | **Effort:** ~4h | **Priority:** P1

- Create `api_team_mappings` table (api_source, api_team_id → team_id)
- Build one-time mapping script matching football-data.org team IDs to existing 325 teams
- Handle name variations between API and Football-Data.co.uk naming
- Schema migration for the new table (uses Task 0b migration system)

### Task 3: Live Ingestion Pipeline
**Role:** `/data-eng` | **Effort:** ~6h | **Priority:** P1

- Create `src/live/ingestion.py` — fetch recent matches, upsert into matches table
- Fetch upcoming fixtures, upsert into fixtures table
- Use `run_incremental_update()` from Task 0c (not full pipeline recompute)
- Scheduled execution: systemd timer or cron (2x daily: 6am, 6pm)

### Task 4: Fixtures Frontend Page
**Role:** `/fullstack` | **Effort:** ~4h | **Priority:** P2

- Create `/fixtures` page showing upcoming matches from fixtures table
- Show pre-match Elo predictions (auto-generated via prediction module)
- Group by competition, sorted by date
- Link to team pages

### Task 5: Tier Weight Optimization
**Role:** `/analyst` | **Effort:** ~8h | **Priority:** P2

- Use Optuna for Bayesian optimization of tier weights (T1-T5)
- Objective: maximize log-likelihood of match outcomes
- Cross-validation on held-out seasons
- Update EloSettings defaults with optimized weights

### Task 6: Prediction Tracking
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
