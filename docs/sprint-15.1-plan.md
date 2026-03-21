# Sprint 15.1 Plan — Accuracy Charts, Elo Deltas & Polish

> Status: COMPLETED
> Depends on: Sprint 15 (completed)
> Milestones: M13 (13b, 13c, 13f, 13g, 13h)

## Goals

Complete the M13 milestone by adding calibration and Brier trend charts to the accuracy detail view, showing Elo rating changes on completed fixtures, polishing logo sizes and breadcrumbs, and bringing API documentation up to date with all 15+ endpoints.

## Current State

- **Calibration data**: `get_prediction_accuracy()` already returns 10-bucket calibration dict (`actual_frequency` vs `expected_midpoint`) and rolling `time_series` array (window=50). Neither is rendered in EloKit
- **Elo change data**: `ratings_history` table stores `rating` (post-match) and `rating_delta` per team per match. Pattern already used in `/api/teams/{team_id}/results` endpoint. The fixtures API exposes pre-match Elo (`prediction.home_elo/away_elo`) but not post-match or delta
- **Logo sizes**: Competition icons 20×20px (`w-5 h-5`), club icons 16×16px (`w-4 h-4`). Breadcrumb and sidebar flags similarly small
- **API docs**: `docs/api-contract.md` is v1.0.0, only documents 7 Sprint 6 endpoints. Missing 10+ endpoints from Sprints 10–15

---

## Scope

### In Scope

- **Task 1**: Frontend — Calibration chart (M13b)
- **Task 2**: Frontend — Brier score time series chart (M13c)
- **Task 3**: Backend + Frontend — Elo change on completed fixtures (M13g)
- **Task 4**: Frontend — Logo & breadcrumb polish (M13h)
- **Task 5**: Documentation — API contract update (M13f)
- **Task 6**: Tests

### Out of Scope

- Chart export (M4.5 — Sprint 16)
- Club logos (M12 Phase 2)
- Bayesian parameter optimization (M5)

---

## Tasks

### Task 1: Frontend — Calibration Chart

**Role:** `/fullstack` | **Effort:** ~2h | **Priority:** P0

Render the 10-bucket calibration data as a bar chart with a diagonal reference line showing perfect calibration.

**Data source:** The `calibration` field from `/api/prediction-accuracy` (already fetched in the detail view from Sprint 15). Structure:

```json
{
  "0-10%": {"count": 450, "actual_frequency": 0.0622, "expected_midpoint": 0.05},
  "10-20%": {"count": 1200, "actual_frequency": 0.1350, "expected_midpoint": 0.15},
  ...
}
```

**Visual design:**
- **Chart type**: ApexCharts bar chart (one bar per bucket) with line overlay for the perfect calibration reference
- **X-axis**: Predicted probability buckets (0-10%, 10-20%, ..., 90-100%)
- **Y-axis**: Frequency (0% to 100%)
- **Bars**: Actual outcome frequency per bucket (blue/teal)
- **Reference line**: Diagonal line from (0%, 0%) to (100%, 100%) showing perfect calibration
- **Tooltip**: "Bucket: 30-40% | Predicted: 35% | Actual: 32.1% | N=1,450"
- **Title**: "Calibration — Predicted vs Actual Outcome Rate"

**Placement:** In the accuracy detail view (Sprint 15), between the Performance Grid and Match Prediction Log.

**Files modified:**
- `backend/templates/index.html` — chart rendering, ApexCharts config

**Exit criteria:**
- [ ] 10-bar calibration chart renders from existing API data
- [ ] Perfect calibration reference line displayed
- [ ] Tooltips show bucket details including sample count
- [ ] Chart respects current navigation scope
- [ ] Empty state handled (no predictions)

---

### Task 2: Frontend — Brier Score Time Series Chart

**Role:** `/fullstack` | **Effort:** ~2h | **Priority:** P0

Render the rolling Brier score trend as an area chart showing model performance over time.

**Data source:** The `time_series` field from `/api/prediction-accuracy`. Structure:

```json
[
  {"date": "2024-08-17", "rolling_brier": 0.5823, "count": 50},
  {"date": "2024-08-18", "rolling_brier": 0.5791, "count": 51},
  ...
]
```

**Visual design:**
- **Chart type**: ApexCharts area chart (filled line)
- **X-axis**: Date (time axis)
- **Y-axis**: Brier score (0.0 to 1.0, inverted sense — lower is better)
- **Reference line**: Horizontal line at Brier = 0.586 (current mean) labeled "Overall Mean"
- **Fill**: Gradient fill below the line (green-tinted when below mean, red-tinted above)
- **Tooltip**: "Date: 2024-08-17 | Rolling Brier: 0.582 | Window: 50 predictions"
- **Title**: "Brier Score Trend (Rolling 50-prediction window)"
- **Zoom**: Enable ApexCharts native zoom

**Placement:** Below the calibration chart in the accuracy detail view.

**Files modified:**
- `backend/templates/index.html` — chart rendering, ApexCharts config

**Exit criteria:**
- [ ] Area chart renders Brier trend over time
- [ ] Mean reference line displayed
- [ ] Tooltips show date and rolling Brier value
- [ ] Zoom enabled
- [ ] Chart respects current navigation scope
- [ ] Empty state handled

---

### Task 3: Backend + Frontend — Elo Change on Completed Fixtures

**Role:** `/fullstack` | **Effort:** ~3h | **Priority:** P1

Show Elo rating change (+12 / -8) for each team on completed match cards in the fixtures widget.

**Backend changes:**

Extend the fixtures/scoped endpoint to include Elo deltas for completed (finished) matches.

**Data source:** `ratings_history` table has `rating_delta` per team per match. For completed fixtures that have been ingested as matches, JOIN `ratings_history` on the match to get deltas.

**Approach:**
1. For finished fixtures, look up the corresponding match by home_team, away_team, and date
2. JOIN `ratings_history` for both home and away teams on that `match_id`
3. Return `home_elo_change` and `away_elo_change` as optional float fields on `ScopedFixtureEntry`

**Response model addition** (in `backend/models.py`):
```python
class ScopedFixtureEntry(BaseModel):
    # ... existing fields ...
    home_elo_change: float | None = None  # NEW: +12.3 or -8.1
    away_elo_change: float | None = None  # NEW
```

**Frontend changes:**
- On finished fixture cards, display the Elo delta next to each team name
- Format: `+12` (green, `text-green-600`) or `-8` (red, `text-red-500`), rounded to nearest integer
- Small text size (`text-xs`) to not clutter the card
- Only show when data is available (not all finished matches may have ratings history)

**Files modified:**
- `backend/models.py` — add `home_elo_change`, `away_elo_change` to `ScopedFixtureEntry`
- `backend/main.py` — JOIN `ratings_history` in fixtures/scoped query for finished matches
- `backend/templates/index.html` — display Elo delta on fixture cards

**Exit criteria:**
- [ ] Finished fixtures show Elo change per team (e.g., `+12` / `-8`)
- [ ] Color-coded: green for positive, red for negative
- [ ] Only displayed for finished matches with ratings data
- [ ] Upcoming fixtures show no Elo change (as expected)
- [ ] API response backward compatible (new fields are nullable)

---

### Task 4: Frontend — Logo & Breadcrumb Polish

**Role:** `/fullstack` | **Effort:** ~1.5h | **Priority:** P2

Increase logo sizes across the UI and ensure breadcrumbs show flag/logo at every navigation level.

**Changes:**

1. **Sidebar logos**: Increase nation flags and competition logos from current sizes to 24×24px (`w-6 h-6`)
2. **Breadcrumb logos**: Increase to 24×24px (`w-6 h-6`); add competition logo at league-level and team-level breadcrumb segments (currently only nation flag shown)
3. **Fixture competition icons**: Increase from `w-5 h-5` (20px) to `w-6 h-6` (24px)

**Current state investigation needed:** Verify exact breadcrumb rendering in `base.html` and `index.html` to identify where logos are missing.

**Files modified:**
- `backend/templates/index.html` — update size classes, add missing logos to breadcrumbs
- `backend/templates/base.html` — if breadcrumbs are rendered there

**Exit criteria:**
- [ ] All logos rendered at 24×24px minimum (up from 16-20px)
- [ ] Breadcrumbs show nation flag at nation/league/team levels
- [ ] Breadcrumbs show competition logo at league/team levels
- [ ] No layout breakage on mobile

---

### Task 5: Documentation — API Contract Update

**Role:** `/tech-writer` | **Effort:** ~3h | **Priority:** P1

Bring `docs/api-contract.md` up to date with all current endpoints. Currently documents 7 Sprint 6 endpoints; needs 10+ more from Sprints 10–15.

**Endpoints to document:**

| Endpoint | Sprint Added | Notes |
|---|---|---|
| `GET /api/rankings/context` | 12 | Team ±3 context ranking |
| `GET /api/fixtures/scoped` | 12 | Scoped fixtures with pagination |
| `GET /api/chart/scoped` | 12 | Rating history for top N teams |
| `GET /api/accuracy/scoped` | 12 | Compact accuracy stats |
| `GET /api/sidebar` | 12 | Navigation tree (nations, leagues, cups) |
| `GET /api/prediction-accuracy` | 10 | Full accuracy with calibration, time series |
| `GET /api/prediction-history` | 10 | Paginated prediction log with search |
| `GET /api/accuracy/grid` | 15 | 3×3 confusion matrix |
| `GET /api/teams/{team_id}/results` | 8 | Team results with Elo data |
| `GET /api/team-stats/{team_id}` | 8 | Team statistics |

**Additional updates:**
- Update data coverage stats: 325 teams, 31,789 matches, 2010–2026
- Document new query parameters: `search`, `country`, `team_id` scoping
- Update changelog with Sprints 7–15.1 additions
- Document response models for all new endpoints

**Files modified:**
- `docs/api-contract.md`

**Exit criteria:**
- [ ] All 17+ endpoints documented with request parameters and response models
- [ ] Data coverage stats updated
- [ ] Changelog updated through Sprint 15.1
- [ ] Examples for key endpoints (fixtures/scoped, prediction-accuracy, accuracy/grid)

---

### Task 6: Tests

**Role:** `/test-runner` | **Effort:** ~2h | **Priority:** P1

**Test cases:**
- `/api/fixtures/scoped` returns `home_elo_change` and `away_elo_change` for finished matches
- `/api/fixtures/scoped` returns `null` for upcoming fixtures' Elo change fields
- Elo change values are correct (match `ratings_history.rating_delta`)
- Regression: all existing 388 tests still pass

**Files modified:**
- `tests/test_backend.py` — new tests for Elo change fields

**Exit criteria:**
- [ ] All new tests pass
- [ ] Full suite: 388+ tests passing, no regressions

---

## Task Dependencies

```
Task 1 (Calibration chart) ─────── Independent (uses existing API)
Task 2 (Brier trend chart) ─────── Independent (uses existing API)
Task 3 (Elo change) ────────────── Backend first, then frontend
Task 4 (Logo polish) ───────────── Independent
Task 5 (API docs) ──────────────── Independent (can run in parallel)
Task 6 (Tests) ─────────────────── After Tasks 1-4

Parallel tracks:
  Track A: Tasks 1 + 2 (both chart work in accuracy detail view)
  Track B: Task 3 (backend + frontend, fixtures widget)
  Track C: Task 4 (CSS/template changes)
  Track D: Task 5 (documentation only)
  Final:   Task 6 (tests after all code changes)
```

## Estimated Effort

| Task | Effort |
|------|--------|
| 1. Calibration chart | ~2h |
| 2. Brier trend chart | ~2h |
| 3. Elo change on fixtures | ~3h |
| 4. Logo & breadcrumb polish | ~1.5h |
| 5. API contract update | ~3h |
| 6. Tests | ~2h |
| **Total** | **~13.5h** |

## Risks

1. **Calibration bucket sparsity**: Extreme buckets (90-100%) may have very few predictions, making the chart look sparse. Mitigation: show count on tooltip so users understand sample size; consider collapsing empty buckets.
2. **Elo change JOIN complexity**: Fixtures are stored separately from matches. Matching a finished fixture to its corresponding match requires joining on team IDs + date. If team IDs don't match exactly (e.g., different sources), some deltas may be missing. Mitigation: use nullable fields, only show when data exists.
3. **Time series length**: With 20K+ predictions, the time series may have thousands of data points. ApexCharts handles this well with zoom, but may need to downsample if rendering is slow.
4. **Breadcrumb structure**: Need to verify how breadcrumbs are currently rendered — if they're pure Alpine.js state, adding logos requires the API to return logo URLs at each navigation level. The sidebar API already has `flag_url` and `logo_url`, so this should be available.

## Definition of Done

- [x] Calibration chart renders 10-bucket predicted-vs-actual with reference line
- [x] Brier trend chart renders rolling score over time with mean reference
- [x] Completed fixtures show Elo change per team (green +N / red -N)
- [x] All logos 24×24px; breadcrumbs show flag+logo at every level
- [x] API contract doc covers all 17+ endpoints with examples
- [x] All tests passing (388, no regressions)
