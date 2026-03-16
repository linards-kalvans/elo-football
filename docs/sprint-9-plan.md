# Sprint 9 Plan — Live Data Groundwork & Calibration Fix

> Status: COMPLETED
> Depends on: Sprint 8 (completed)
> Completed: 2026-03-15

## Goals

1. **Elo calibration fix** — Warm-up period with 2010-2016 data so teams start at realistic ratings
2. **Database schema expansion** — Fixtures & predictions tables for live data (M8) and prediction tracking (M9)
3. **Live data API research** — ADR comparing football-data.org, API-Football, TheSportsDB
4. **Test coverage expansion** — Target 200+ tests (achieved 237)
5. **TemplateResponse cleanup** — Already done in Sprint 8

## Completed Tasks

### Task 1: Starlette TemplateResponse Deprecation Cleanup
**Status:** Already done (Sprint 8)
- TemplateResponse calls already use new signature `TemplateResponse(request, name, context)`

### Task 2: Database Schema — Fixtures & Predictions Tables
**Status:** COMPLETED
- Added `fixtures` table: id, date, home/away team IDs, competition_id, season, status, external_api_id, last_updated
- Added `predictions` table: id, match_id/fixture_id, predicted_at, p_home, p_draw, p_away, home_elo, away_elo
- CHECK constraint: exactly one of match_id/fixture_id set
- UNIQUE constraint on fixtures (date, home_team_id, away_team_id, competition_id)
- Indexes: idx_fixtures_status, idx_fixtures_date, idx_predictions_fixture, idx_predictions_match
- Repository functions: insert_fixture, get_upcoming_fixtures, update_fixture_status, insert_prediction, get_predictions_for_fixture

### Task 3: Initial Elo Calibration Fix (M10)
**Status:** COMPLETED
- Extended `data/fetch_league_csvs.sh` to include seasons 1011-1516 (6 extra seasons × 5 leagues = 30 files)
- Downloaded 80 total CSVs (16 seasons × 5 leagues), all successful
- Added `display_from_date` to EloSettings (default "2016-08-01", env-configurable via ELO_DISPLAY_FROM_DATE)
- Updated API endpoints to filter by display_from_date (team history, peak/trough stats)
- Pipeline re-run: 31,789 matches (up from 20,833), 325 teams, 63,578 rating entries
- Validation: Aug 2016 starting ratings — Barcelona 1813, Real Madrid 1805, Bayern 1801 (no team at exactly 1500)

### Task 4: Live Data API Research & ADR
**Status:** COMPLETED
- Evaluated football-data.org, API-Football, TheSportsDB
- Recommendation: football-data.org (free tier) — 8/8 competitions, 10 calls/min, $0/year
- Written to `docs/adr-004-live-data-source.md`

### Task 5: Test Coverage Expansion
**Status:** COMPLETED (237 tests, target was 200+)
- Elo engine: +10 tests (extreme scorelines, long time gaps, rating floor, tier boundaries)
- Pipeline: +5 tests (result constraints, empty DB, multi-match edge cases, validation)
- Backend API: +19 tests (404s, invalid dates, future dates, special chars, validation errors, edge cases)
- European data: +8 tests (parser edge cases, stage classification, normalization)
- Prediction: +6 tests (edge cases, boundary probabilities, custom settings)
- New tables: +20 tests (fixture CRUD, prediction CRUD, constraint violations, schema checks)

### Task 6: Documentation Update
**Status:** COMPLETED
- Updated sprint-9-plan.md with completed task details
- Updated CLAUDE.md with Sprint 9 completion
- Drafted sprint-10-plan.md outline

## Metrics

| Metric | Before | After |
|--------|--------|-------|
| Tests | 164 | 237 |
| Matches | 20,833 | 31,789 |
| Teams | 300 | 325 |
| Rating entries | ~40K | 63,578 |
| Deprecation warnings | 0 | 0 |
| DB tables | 5 | 7 (+ fixtures, predictions) |
