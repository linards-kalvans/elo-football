# Sprint 15.2 Plan — Accuracy Bug Fixes

> Status: PLANNED
> Depends on: Sprint 15.1 (completed)
> Milestones: M9, M13

## Goals

Fix two regressions in the accuracy detail view discovered after Sprint 15.1:

1. **Brier score trend shows only 2 data points** — the rolling chart uses `scored_at` as the time axis, but all backfilled predictions share the same `scored_at` timestamp (when the backfill script ran). Fix: use match date as the time axis.
2. **Match Prediction Log is empty in non-team scopes** — the prediction history list is empty when viewing global, nation, or league context; it only works for team context. The `country`/`competition` JOIN filters appear to produce 0 rows in wider scopes.

---

## Bug Analysis

### Bug 1: Brier score trend — only 2 dates

**Root cause:** `_compute_brier_time_series()` in `src/live/prediction_tracker.py` uses `scored_at` to assign each data point a date and deduplicates to one point per date. All 20,263 backfilled predictions have `scored_at` = the timestamp when the backfill script ran (one or two distinct dates). Result: the chart shows 1–2 points instead of ~3,000 daily points spanning 2016–2026.

**Fix:** Pass match date (`COALESCE(m.date, f.date)`) to `_compute_brier_time_series()` and use it for ordering and date bucketing. The query in `get_prediction_accuracy()` must include the match date in its SELECT.

**Secondary fix:** After each daily update, new live predictions get scored immediately — these do have meaningful `scored_at` timestamps. But the time axis should still be match date for consistency. Ongoing daily updates will add new points at the correct date going forward.

### Bug 2: Match Prediction Log empty in wider scopes

**Root cause (hypothesis):** The `get_prediction_history()` query filters via `COALESCE(c1.country, c2.country)` and `COALESCE(c1.name, c2.name)`. For backfilled predictions, `p.match_id` is set, so `c1` resolves via `LEFT JOIN competitions c1 ON c1.id = m.competition_id`. However, the frontend `buildParams()` sends `competition` **and** `country` simultaneously for league-level context — the backend only uses `competition` in that case (due to `if competition: ... elif country:`), which is correct. The exact failure path needs to be traced by:

1. Running the query directly with `competition = "Premier League"` and checking for rows
2. Checking if `c1.name` matches exactly (potential trailing space, encoding issue, or synonym like "EPL" vs "Premier League")
3. Checking whether the global scope (`p.brier_score IS NOT NULL` only) also returns 0, which would indicate a completely different problem

**Note:** If global scope returns 0 rows, the issue is not the filter logic but something higher up — possibly the frontend not calling `fetchHistory()` at all (e.g., an `x-show` condition blocking the detail panel from mounting, or a JS exception silently aborting the fetch).

---

## Scope

### In Scope

- **Task 1**: Fix Brier trend time axis to use match date
- **Task 2**: Diagnose and fix prediction history empty state in non-team scopes
- **Task 3**: Tests

### Out of Scope

- Sprint 16 (M4.5: chart export, presets) — not blocked by these bugs
- Any new features

---

## Tasks

### Task 1: Fix Brier Trend Time Axis

**Role:** `/fullstack` | **Effort:** ~2h | **Priority:** P0

**Backend changes** (`src/live/prediction_tracker.py`):

1. Add `COALESCE(m.date, f.date) as match_date` to the SELECT in `get_prediction_accuracy()`
2. Change `ORDER BY p.scored_at ASC` → `ORDER BY COALESCE(m.date, f.date) ASC, p.id ASC` so rows arrive in chronological match-date order
3. Update `_compute_brier_time_series()` signature to accept `date_field` (default `"scored_at"`) or just always use `match_date`:
   - Replace `scored_at[:10]` with `row["match_date"]` for the `point_date` assignment

**Expected result:** The Brier trend chart shows ~daily data points from 2016-08-01 to present (~3,500 points), deduped to one per day. The rolling 50-prediction window will still produce a smooth curve.

**Files modified:**
- `src/live/prediction_tracker.py`

**Exit criteria:**
- [ ] `get_prediction_accuracy()` returns `time_series` with one entry per match-day (not per scored_at date)
- [ ] Time series spans from ~2016-08 to present (~3,000+ points)
- [ ] Rolling Brier chart visually shows long-term trend, not 2 points
- [ ] Existing `time_series` field format unchanged (`date`, `rolling_brier`, `count`)

---

### Task 2: Fix Prediction History in Non-Team Scopes

**Role:** `/fullstack` | **Effort:** ~3h | **Priority:** P0

**Investigation steps (before coding):**

1. Run `GET /api/prediction-history?page=1&per_page=5` (global, no filters) directly and check response. If `total > 0`, the backend is fine and the issue is frontend.
2. Run `GET /api/prediction-history?country=England&page=1&per_page=5` and check.
3. Run `GET /api/prediction-history?competition=Premier+League&page=1&per_page=5` and check.

**Likely fix paths:**

**Path A (backend):** If queries return 0 for non-team scopes, the JOIN-based filter is broken. Fix by:
- Checking the exact `country` values in the `competitions` table vs what the frontend passes
- Possibly the `country` param from the template is URL-encoded differently — ensure the `buildParams()` passes the raw display name (e.g., `"England"` not `"england"`)
- Ensure `COALESCE(c1.country, c2.country)` correctly resolves when `c2` is NULL (backfilled, no fixture)

**Path B (frontend):** If backend returns data but the list is empty, investigate:
- Whether `fetchHistory()` is called when `openAccuracyDetail()` is triggered in non-team contexts
- Whether an `x-show` condition on the match table is evaluating incorrectly
- Whether `historyData.items` is being overwritten after the fetch completes

**Files potentially modified:**
- `src/live/prediction_tracker.py` — fix JOIN filter for country/competition scopes
- `backend/templates/index.html` — fix frontend fetch or rendering if Path B

**Exit criteria:**
- [ ] `GET /api/prediction-history` (no filters) returns predictions with `total > 0`
- [ ] `GET /api/prediction-history?country=England` returns EPL/domestic England predictions
- [ ] `GET /api/prediction-history?competition=Premier+League` returns Premier League predictions
- [ ] Match Prediction Log is populated when viewing global, nation, and league contexts in EloKit
- [ ] Team scope still works (regression check)

---

### Task 3: Tests

**Role:** `/test-runner` | **Effort:** ~1.5h | **Priority:** P1

**New test cases:**
- `get_prediction_accuracy()` returns `time_series` with entries spanning multiple dates (not all the same date)
- `time_series` entries use match dates, not `scored_at` dates
- `get_prediction_history()` with no filters returns predictions
- `get_prediction_history(country="England")` returns only England-competition predictions
- `get_prediction_history(competition="Premier League")` returns only EPL predictions
- Regression: `get_prediction_history(team_id=X)` still works

**Files modified:**
- `tests/test_prediction_tracker.py`
- `tests/test_backend.py` — `/api/prediction-history` with country/competition params

**Exit criteria:**
- [ ] All new tests pass
- [ ] Full suite: 388+ tests, no regressions

---

## Task Dependencies

```
Task 1 (Brier trend fix)   ─── Independent (backend only)
Task 2 (History fix)       ─── Independent (investigate first, then code)
Task 3 (Tests)             ─── After Tasks 1 & 2
```

---

## Definition of Done

- [ ] Brier trend chart shows full history from 2016 to present (not 2 points)
- [ ] Match Prediction Log populated at global, nation, and league scopes
- [ ] 388+ tests passing, no regressions
