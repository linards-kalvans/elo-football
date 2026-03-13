# Sprint 5 — Data Pipeline & Persistence

**Depends on:** Sprint 4 completed (unified cross-league ratings working)
**Status:** NOT STARTED
**Goal:** Move from ad-hoc scripts to a production-grade data pipeline with persistent storage, automated refresh, and a queryable API layer.

---

## Items

### 0. Storage Engine Architecture Decision

**Priority:** P1 | **Impact:** High | **Blocks:** all other items in this sprint

Before building the pipeline, produce an Architecture Decision Record (ADR) evaluating storage options against project requirements.

**Options to evaluate:**

| Option | Pros | Cons | Best for |
|--------|------|------|----------|
| **SQLite** | Zero-ops, single file, embedded, great for read-heavy workloads | Single-writer, no concurrent writes, harder to scale | Single-server deploy, MVP |
| **PostgreSQL** | Concurrent writes, full SQL, extensions (TimescaleDB), battle-tested | Requires server management, heavier for a small project | Multi-user, production scale |
| **DuckDB** | Columnar, excellent for analytics, embeddable like SQLite | Less mature for serving workloads, no concurrent writers | Analytics-first, batch queries |
| **Parquet files + query engine** | Simple, portable, great for batch analytics | No transactional updates, not suitable for live serving | Pure analytics, no web app |

**Evaluation criteria:**
- Read/write ratio (heavily read-biased — ratings update once per matchday)
- Query patterns (rankings at date X, team trajectory, upcoming match predictions)
- Data volume estimate (5 leagues × 10 seasons × ~380 matches ≈ 19k rows; grows ~1,900/year)
- Deployment model (single server vs. cloud, containerized vs. bare)
- ORM vs. raw SQL (SQLAlchemy, raw queries, lightweight mapper)
- Migration path if needs grow

**Deliverables:**
- ADR document: `docs/adr-storage-engine.md`
- Schema design for chosen engine

**Note:** Data volume is small enough that any option works technically. The decision is about operational simplicity vs. future flexibility.

### 1. Schema Design & Database Setup

**Priority:** P1 | **Impact:** High | **Depends on:** item 0

Design and implement the database schema for the chosen storage engine.

**Core tables/entities:**

| Table | Purpose | Key columns |
|-------|---------|-------------|
| `teams` | Canonical team registry | `id`, `name`, `country`, `aliases[]` |
| `competitions` | Competition registry | `id`, `name`, `tier`, `canonical_id` |
| `matches` | All match results | `id`, `date`, `home_team_id`, `away_team_id`, `home_goals`, `away_goals`, `competition_id`, `season` |
| `ratings_history` | Point-in-time Elo snapshots | `team_id`, `date`, `rating`, `competition_id` |
| `parameters` | Engine config snapshots | `run_id`, `k_factor`, `spread`, ... |

**Deliverables:**
- Migration scripts or schema creation code
- Seed script to load existing CSV data into the database
- Index strategy for common query patterns

### 2. Data Refresh Pipeline

**Priority:** P2 | **Impact:** Medium | **Depends on:** item 1

Automate the end-to-end flow: fetch new results → ingest → recompute ratings → persist.

**Deliverables:**
- Pipeline script (`src/pipeline.py` or similar) orchestrating:
  1. Fetch latest match data from source(s)
  2. Validate and normalize new records
  3. Append to database
  4. Recompute ratings (full or incremental)
  5. Update `ratings_history`
- Idempotent: re-running the pipeline produces the same result
- Logging: record what was fetched, how many new matches, any validation failures
- Schedulable via cron or similar (document the invocation)

### 3. Match Prediction API (Python)

**Priority:** P2 | **Impact:** Medium | **Depends on:** item 1

Expose match predictions as a Python API (internal, pre-FastAPI).

**Deliverables:**
- `engine.predict_match(home_team, away_team, date=None)` returning:
  - Home win probability, draw probability, away win probability
  - Current Elo ratings for both teams
  - Rating-based confidence level
- Uses latest ratings from the database (or in-memory if no DB yet)
- Unit tests for prediction outputs

### 4. Data Validation & Monitoring

**Priority:** P3 | **Impact:** Low | **Depends on:** item 2

Guard against silent data issues as the pipeline runs over time.

**Deliverables:**
- Schema drift detection (unexpected columns, type changes in source CSVs)
- Completeness checks (expected match count per league per season)
- Duplicate detection (same match appearing twice)
- Alerting: log warnings for anomalies, fail loudly on critical issues

---

## Acceptance Criteria

- [ ] ADR for storage engine written and decision made
- [ ] Database schema implemented and populated with all existing data
- [ ] Pipeline runs end-to-end: fetch → ingest → rate → persist
- [ ] Pipeline is idempotent and logged
- [ ] `predict_match()` returns calibrated probabilities
- [ ] Validation catches at least: duplicates, missing matches, schema drift

## Out of Scope

- FastAPI HTTP layer (Sprint 6)
- Frontend (Sprint 6–7)
- Real-time / live match updates
