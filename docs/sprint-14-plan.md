# Sprint 14 Plan — Prediction Pipeline Fix & Historical Backfill

> Status: COMPLETED (2026-03-17)
> Depends on: Sprint 13 (completed)
> Milestones: M9 (Prediction Tracking & Validation — 9a.1, 9a.2, 9b)

## Goals

Fix the end-to-end prediction scoring pipeline so live predictions are scored after match completion, add retry logic for transient HTTP 403 errors in the daily update, and backfill historical predictions so the accuracy dashboard is populated from day one.

**Current state:** The daily update script runs successfully (matches ingested, fixtures fetched, predictions generated for new fixtures), but:
1. No prediction accuracy data appears on the dashboard — the scoring step may not be running, or predictions may not be linked to completed matches correctly.
2. HTTP 403 from football-data.org kills the daily update immediately (treated as permanent auth failure).
3. The 25K+ post-2016 historical matches have no stored predictions, leaving the accuracy/history pages empty.

## Scope

### In Scope
- Debug and fix prediction scoring pipeline (Task 1)
- Add 403 retry logic to daily update (Task 2)
- Backfill historical predictions with Brier scores (Task 3)
- Frontend: label backfilled vs live predictions (Task 4)
- Tests for all new functionality (Task 5)

### Out of Scope
- Chart export (M4.5, Sprint 15)
- Club logos (M12 Phase 2)
- Parameter optimization (M5)
- Performance alerts for model degradation (M9 9c — future sprint)

---

## Tasks

### Task 1: Debug & Fix Prediction Scoring Pipeline
**Role:** `/data-eng` | **Effort:** ~3h | **Priority:** P0

**Problem:** `score_completed_matches()` in `src/live/prediction_tracker.py` exists but may not be called during the daily update, or the join conditions may not match predictions to completed matches.

**Investigation steps:**
1. Check if `score_completed_matches()` is called anywhere in `run_daily_update()` → **it is not**. The daily update fetches matches and fixtures but never scores predictions.
2. Check if fixture status transitions from `scheduled` → `completed` when a match is ingested — currently `fetch_and_ingest_matches()` ingests matches via `run_incremental_update()` but does not update the fixtures table status.
3. Verify the join in `score_completed_matches()` works: predictions are linked via `fixture_id`, but scoring joins `fixtures f → matches m ON m.date = f.date AND m.home_team_id = f.home_team_id AND m.away_team_id = f.away_team_id`. This should work if dates match exactly.

**Fix:**
1. Add `score_completed_matches()` call to `run_daily_update()` (after match ingestion and before fixture fetch, or at the end).
2. Add fixture status update: when a match is ingested that matches an existing fixture (same date + teams), update the fixture status to `completed`.
3. Add summary output for scoring results in the daily update script.

**Files modified:**
- `src/live/ingestion.py` — add scoring call to `run_daily_update()`, add fixture status update to `fetch_and_ingest_matches()`
- `scripts/run_daily_update.py` — display scoring summary

**Exit criteria:**
- [x] `score_completed_matches()` is called during daily update
- [x] Fixtures are marked `completed` when their match result is ingested
- [x] Predictions with matching completed matches receive Brier scores
- [x] Daily update summary shows scoring stats

---

### Task 2: Add HTTP 403 Retry to Daily Update
**Role:** `/data-eng` | **Effort:** ~1h | **Priority:** P1

**Problem:** `FootballDataClient._request()` raises `AuthError` immediately on 401/403. football-data.org occasionally returns transient 403s (rate-limit-adjacent, server-side issues), causing the entire daily update to fail.

**Fix:** In `_request()`, distinguish between permanent auth failure (missing/invalid key) and transient 403:
- If the API key is known to be valid (it was set and formatted correctly), treat 403 as retryable with longer delays: 10s, 60s, 120s.
- Keep 401 as non-retryable (truly invalid credentials).
- Add a `max_403_retries` parameter (default 3) to the client.

**Implementation:**
```python
# In _request(), replace the 401/403 block:
if response.status_code == 401:
    raise AuthError(response.text)

if response.status_code == 403:
    if attempt < MAX_RETRIES - 1:
        delays = [10, 60, 120]
        wait = delays[min(attempt, len(delays) - 1)]
        logger.warning("HTTP 403 on attempt %d, retrying in %ds...", attempt + 1, wait)
        await asyncio.sleep(wait)
        continue
    raise AuthError(f"Persistent 403 after {MAX_RETRIES} attempts: {response.text}")
```

**Files modified:**
- `src/live/football_data_client.py` — split 401/403 handling, add 403 retry with escalating delays

**Exit criteria:**
- [x] 401 raises `AuthError` immediately (no change)
- [x] 403 retries up to 3 times with delays of 10s, 60s, 120s
- [x] After 3 failed 403 attempts, raises `AuthError`
- [x] Retry behavior is logged

---

### Task 3: Backfill Historical Predictions
**Role:** `/data-eng` + `/analyst` | **Effort:** ~4h | **Priority:** P0

**Problem:** Only live fixtures (from Sprint 10 onward) have predictions. The ~25K post-2016 matches have no stored predictions, so the accuracy dashboard and history page are empty.

**Solution:** Create a backfill script that replays the Elo computation chronologically. Before processing each match, use the **pre-match ratings** to generate a prediction, store it linked to the match, then let the engine update ratings and compute the Brier score.

**Implementation:**
1. New script: `scripts/backfill_predictions.py`
2. Load all matches from the database ordered by date
3. Filter to matches on or after `display_from_date` (2016-08-01)
4. For each match (in chronological order):
   a. Get current ratings for home and away teams (pre-match)
   b. Generate prediction using `predict_match()`
   c. Insert prediction with `match_id` (not `fixture_id`), `source='backfill'`
   d. Compute Brier score immediately from the known result
   e. Store prediction with `brier_score` and `scored_at`
5. Skip matches where a prediction already exists (idempotent)
6. Use the EloEngine's intermediate state — need to either:
   - Run `compute_ratings()` step-by-step and intercept pre-match ratings, OR
   - Query `ratings_history` for each match's pre-match state (simpler but slower)

**Preferred approach:** Query `ratings_history` for the rating just before each match date. This is simpler and leverages existing data, though slower. For ~25K matches this should still complete in <5 minutes.

**Schema change:** Add `source` column to `predictions` table (migration 005):
```sql
ALTER TABLE predictions ADD COLUMN source TEXT DEFAULT 'live';
```
Then update backfill to set `source = 'backfill'`.

**Files created/modified:**
- `scripts/backfill_predictions.py` — new backfill script
- `src/db/migrations/005_prediction_source.sql` — new migration
- `src/db/repository.py` — add `source` parameter to `insert_prediction()`
- `src/live/prediction_tracker.py` — update queries to optionally filter by source

**Exit criteria:**
- [x] Backfill script generates predictions for all post-2016 matches (~25K)
- [x] Each prediction uses pre-match ratings (not post-match)
- [x] Predictions marked with `source = 'backfill'`
- [x] Brier scores computed for all backfilled predictions
- [x] Script is idempotent (safe to re-run)
- [x] Completes in <10 minutes

---

### Task 4: Frontend — Label Backfill vs Live Predictions
**Role:** `/fullstack` | **Effort:** ~1.5h | **Priority:** P2

**Problem:** Backfilled predictions were generated in hindsight (parameters were tuned on this data), so they should be visually distinguished from live predictions.

**Deliverables:**
1. **Accuracy dashboard** (`/api/accuracy/scoped`): Add `live_brier_score` and `backfill_brier_score` breakdown to accuracy stats
2. **Prediction history** (`/api/prediction-history`): Add `source` field to each prediction entry
3. **Frontend**: Show a subtle badge/label on backfilled predictions ("Backfill" vs "Live") in the prediction history list
4. **Accuracy widget**: If both live and backfill data exist, show both scores with a note explaining the difference

**Files modified:**
- `backend/main.py` — pass source filter to accuracy/history endpoints
- `backend/models.py` — add `source` field to prediction history response
- `src/live/prediction_tracker.py` — add source filter to `get_prediction_accuracy()` and `get_prediction_history()`
- `backend/templates/index.html` — prediction history badge, accuracy breakdown

**Exit criteria:**
- [x] Prediction history shows "Live" or "Backfill" badge per entry
- [x] Accuracy dashboard shows separate stats for live vs backfill
- [x] Backfill label is subtle (not alarming) — e.g., gray pill badge

---

### Task 5: Tests
**Role:** `/test-runner` | **Effort:** ~2h | **Priority:** P1

**Deliverables:**
- Test `score_completed_matches()` is called in daily update flow
- Test fixture status transitions to `completed` after match ingestion
- Test 403 retry logic (mock 403 → 403 → 200 sequence)
- Test 401 still raises immediately
- Test backfill script generates correct predictions (small test dataset)
- Test `source` column filtering in accuracy/history queries
- Full regression suite: all existing tests pass

**Exit criteria:**
- [x] All new tests pass
- [x] Full suite: 364+ tests passing, no regressions

---

## Task Dependencies

```
Task 1 (Fix scoring pipeline) ──▶ Task 3 (Backfill — needs working scoring)
Task 2 (403 retry)            ──  (independent)
Task 3 (Backfill)             ──▶ Task 4 (Frontend labels — needs source column)

Task 1, 2, 3, 4 ──▶ Task 5 (Tests)
```

**Parallel tracks:**
- Task 1 + Task 2 can run in parallel (independent fixes)
- Task 3 depends on Task 1 (scoring pipeline must work)
- Task 4 depends on Task 3 (needs `source` column)

## Estimated Effort

| Task | Effort |
|------|--------|
| 1. Fix prediction scoring pipeline | ~3h |
| 2. HTTP 403 retry | ~1h |
| 3. Historical prediction backfill | ~4h |
| 4. Frontend source labels | ~1.5h |
| 5. Tests | ~2h |
| **Total** | **~11.5h** |

## Risks

1. **Backfill performance**: Querying `ratings_history` per match for 25K matches could be slow. Mitigation: batch queries by date, or use the engine's in-memory state during a single `compute_ratings()` pass.
2. **Pre-match rating accuracy**: The backfill must use ratings *before* each match is processed. If we query `ratings_history`, we need the rating entry just before the match date, not the one created by the match itself. Must handle carefully.
3. **Prediction table constraints**: The `predictions` table has a CHECK constraint (`match_id IS NOT NULL XOR fixture_id IS NOT NULL`). Backfill inserts use `match_id` — should work but needs verification.
4. **Duplicate predictions**: If the backfill is run twice, it must not create duplicate predictions. Use `INSERT OR IGNORE` or check for existing predictions before inserting.
5. **Misleading accuracy**: Backfilled predictions will look better than true out-of-sample because parameters were tuned on this data. Clear labeling (Task 4) mitigates this.

## Definition of Done

- [x] Daily update scores predictions for completed matches (Brier scores appear on dashboard)
- [x] Fixture status correctly transitions to `completed` when match result is ingested
- [x] HTTP 403 errors are retried (3 attempts: 10s, 60s, 120s delays) before failing
- [x] Historical predictions backfilled for all post-2016 matches (~25K)
- [x] Backfilled predictions clearly labeled as such in the UI
- [x] Accuracy dashboard populated with thousands of data points
- [x] All tests passing (364+, no regressions)
