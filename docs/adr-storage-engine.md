# ADR: Storage Engine Selection

**Status:** Accepted
**Date:** 2026-03-13
**Decision makers:** Project team

## Context

Sprint 4 completed cross-league calibration: 20,833 matches, 300 teams, unified Elo ratings. Everything runs in-memory from CSVs and openfootball `.txt` files. Sprint 5 introduces persistent storage and an automated pipeline to unblock the Sprint 6 web API.

### Scale Projection (M6 — Full UEFA Coverage)

| Metric | Current | Full scale |
|--------|---------|------------|
| Matches | ~20k | ~250k ceiling |
| Teams | 300 | 2,000+ |
| Ratings history rows | ~60k | ~500k |
| DB file size | ~5 MB | ~50-100 MB |
| Growth rate | — | ~15k matches/year |

## Decision

**SQLite** with WAL mode, raw SQL + Pydantic models, `aiosqlite` for async FastAPI reads.

## Options Evaluated

### 1. SQLite (selected)

- **Scales to our ceiling** — 250k matches, 500k rating rows, 2k teams is trivial
- **Zero ops** — no server process, no credentials, no Docker sidecar; single file
- **Read-heavy workload** — WAL mode handles concurrent web readers + single batch writer
- **Async support** — `aiosqlite` integrates cleanly with FastAPI
- **FTS5** — built-in full-text search for multi-language team name lookup
- **Ships fast** — no infra setup, start coding immediately
- **Migration path** — if we ever need Postgres, SQL is nearly identical

### 2. PostgreSQL (rejected)

- Massive over-engineering for a single-server, sub-100 MB dataset
- Requires running a server process, managing credentials, Docker sidecar
- Operational overhead with no benefit at our scale

### 3. DuckDB (rejected)

- No async driver — incompatible with FastAPI's async model
- Optimized for OLAP (analytical scans), not web-serving point queries
- Poor fit for the read pattern (single-team lookups, latest ratings)

### 4. Parquet files (rejected)

- No indexing, no point queries — dead end for a web application
- Append-only; updates require rewriting entire files
- No transaction support

## Raw SQL + Pydantic over SQLAlchemy

- 5 tables, handful of queries — ORM adds complexity for zero benefit
- Pydantic models already exist for FastAPI response schemas (double duty)
- SQLAlchemy async adds `greenlet` dependency and subtle session management
- Raw SQL is more transparent, easier to optimize, easier to debug

## Schema

5 tables + 1 FTS virtual table:

- `teams` — id, name, country, aliases (JSON array)
- `teams_fts` — FTS5 virtual table over name + aliases for search
- `competitions` — id, name, tier, country
- `matches` — id, date, home/away team IDs, goals, result, competition, season (UNIQUE dedup constraint)
- `ratings_history` — id, team_id, match_id, date, rating, rating_delta
- `parameters` — id, run_timestamp, settings snapshot, matches_processed

## Consequences

### Positive

- Zero infrastructure cost and operational burden
- Single-file backup/restore (`cp data/elo.db data/elo.db.bak`)
- Fast development iteration — no migrations framework needed at this scale
- FTS5 handles team search with multi-language aliases efficiently

### Negative

- Single-writer limitation (acceptable: only batch pipeline writes)
- No built-in replication (acceptable: single-server deployment)
- Must handle schema changes manually (acceptable: 5 stable tables)

### Risks

- If concurrent write load increases significantly, would need to migrate to Postgres
- Mitigation: SQL is standard; migration would be straightforward
