# Sprint 15 Plan — Detailed Prediction Accuracy View

> Status: COMPLETED
> Depends on: Sprint 14 (completed)
> Milestones: M13 (Detailed Prediction Accuracy View)

## Goals

Build a rich, detailed prediction accuracy view within EloKit. The two headline features are:

1. **Prediction Performance Grid** — a 3×3 matrix showing predicted outcome (H/D/A) vs actual outcome, giving users an instant visual breakdown of where the model succeeds and where it fails
2. **Match Prediction Log** — a paginated, searchable table of all scored predictions with multi-word team search (e.g. "Liverpool United" finds both "Liverpool vs Man United" and "Leeds United vs Liverpool")

Additionally, surface the existing rich API data (calibration buckets, Brier time series) that already exists but isn't rendered in the EloKit UI.

## Current State

- **`/api/accuracy/scoped`** — returns `accuracy_pct`, `mean_brier_score`, `trend_pct`, `total_predictions` for current context (country/competition/team)
- **`/api/prediction-accuracy`** — returns rich aggregate data: calibration buckets (10), time_series (rolling Brier), by_competition, by_source, median_brier, recent_form. **Not rendered in EloKit** — only used by the retired old accuracy page
- **`/api/prediction-history`** — returns paginated scored predictions with team names, scores, probabilities, Brier scores. Supports `competition`, `date_from`, `date_to`, `source` filters. **No team name search**
- **Frontend accuracy widget** — compact card showing accuracy %, trend badge, Brier score, count. "View all" link expands inline to show by-source and per-competition table. No navigation to a detail view
- **20,263 scored predictions** in the database (backfill + live)

### What's Missing

1. No confusion matrix / outcome grid anywhere
2. No team search on prediction history
3. Calibration chart data exists in API but never rendered
4. Brier time series data exists in API but never rendered
5. No way to drill into the detailed accuracy view from the compact widget
6. `/api/prediction-accuracy` and `/api/prediction-history` don't support `country` or `team_id` scoping (only `competition` and `source`)

---

## Design Discussion: Prediction Performance Grid

### What It Shows

A 3×3 grid where:
- **Columns** = Predicted outcome (the model's highest-probability pick: Home, Draw, Away)
- **Rows** = Actual outcome (H, D, A)

Each cell shows:
- Count of matches
- Percentage of that actual outcome row (e.g., "of 8,000 actual Home wins, the model predicted Home 65% of the time")
- Cell color intensity proportional to count (heatmap style)

The diagonal represents correct predictions — these cells should be highlighted (green tint). Off-diagonal cells are misclassifications.

### Example Layout

```
                    ── Predicted ──
                    Home    Draw    Away
Actual  Home    │  5,200  │  1,800  │  1,000  │  = 8,000
        Draw    │  1,900  │  1,500  │    600  │  = 4,000
        Away    │  2,100  │  1,300  │  4,863  │  = 8,263
                                                  20,263
```

### Why This Is Useful

- **Draw prediction weakness**: Elo models notoriously under-predict draws. The grid makes this immediately visible — the Draw column will likely be thin compared to Home/Away
- **Home bias**: Users can see if the model over-predicts home wins
- **Asymmetric errors**: Is the model more likely to predict Home when Away wins, or vice versa? The off-diagonal cells reveal this
- **Per-context insights**: When scoped to a team, the grid shows how well the model predicts *that team's* matches specifically

### Naming

"Prediction Performance Grid" — communicates what it is without jargon. Alternative considered: "Outcome Breakdown Matrix" — slightly more descriptive but longer. The column/row headers ("Predicted" / "Actual") provide all the context needed.

---

## Design Discussion: Match Prediction Log

### Search Behavior

The search must work across **both home and away team names simultaneously**. Each search term is matched independently against the concatenation of both team names.

**Algorithm**: Split the search query into whitespace-separated tokens. A match passes the filter if **every token** appears in either the home team name OR the away team name (case-insensitive).

Examples:
| Search query | Finds | Why |
|---|---|---|
| `Liverpool United` | Liverpool vs Man United | "Liverpool" in home, "United" in away |
| `Liverpool United` | Leeds United vs Liverpool | "United" in home, "Liverpool" in away |
| `Liverpool United` | Liverpool vs Sheffield United | Both tokens in home+away |
| `Liverpool` | All Liverpool matches | Single token in either team |
| `Bayern Madrid` | Bayern Munich vs Real Madrid | One token per team |

This is implemented server-side in the `/api/prediction-history` endpoint as a `search` query parameter. The SQL uses `LIKE` with each token against both home and away team names.

### Table Columns

| Column | Content |
|---|---|
| Date | Match date (YYYY-MM-DD) |
| Match | Home Team vs Away Team (with score underneath, e.g. "2 - 1") |
| Competition | Competition name (with logo if available) |
| Prediction | Probability bars: H% / D% / A% with the predicted winner highlighted |
| Result | Actual outcome badge: "H", "D", or "A" with color |
| Brier | Score with color gradient (green=good, red=bad) |
| Correct | Checkmark or X icon |

### Pagination

- Server-side pagination (already exists in `/api/prediction-history`)
- 20 items per page (configurable)
- Page navigation: prev/next + page number display
- Total count displayed

---

## Scope

### In Scope

- **Task 1**: Backend — Prediction Performance Grid API endpoint
- **Task 2**: Backend — Add team search to prediction history API
- **Task 3**: Backend — Scope `/api/prediction-accuracy` to support `country` and `team_id`
- **Task 4**: Frontend — Detailed accuracy view (new panel/section in EloKit)
- **Task 5**: Frontend — Prediction Performance Grid component
- **Task 6**: Frontend — Match Prediction Log with search and pagination
- **Task 7**: Tests

### Out of Scope

- Calibration chart visualization (deferred — data exists in API, frontend chart is separate task)
- Brier time series chart (deferred — same as above)
- Elo change on completed fixtures (M13f — separate sprint)
- Logo size and breadcrumb polish (M13g — separate sprint)
- Chart export (M4.5)
- Club logos (M12 Phase 2)

---

## Tasks

### Task 1: Backend — Prediction Performance Grid API

**Role:** `/fullstack` | **Effort:** ~2h | **Priority:** P0

New endpoint: `GET /api/accuracy/grid`

**Request parameters** (same scoping as `/api/accuracy/scoped`):
- `country` (optional) — filter by country
- `competition` (optional) — filter by competition
- `team_id` (optional) — filter by team ID
- `source` (optional) — filter by prediction source

**Response model:**

```python
class OutcomeGridCell(BaseModel):
    count: int           # Number of matches in this cell
    pct_of_row: float    # Percentage of the actual outcome row (0-100)
    pct_of_total: float  # Percentage of all predictions (0-100)

class OutcomeGridRow(BaseModel):
    predicted_home: OutcomeGridCell
    predicted_draw: OutcomeGridCell
    predicted_away: OutcomeGridCell
    total: int           # Row total (all matches with this actual outcome)

class PredictionGridResponse(BaseModel):
    actual_home: OutcomeGridRow
    actual_draw: OutcomeGridRow
    actual_away: OutcomeGridRow
    total: int
    correct: int
    accuracy_pct: float
```

**Implementation:**
- Query predictions with `brier_score IS NOT NULL` (scored predictions only)
- For each prediction, determine predicted outcome = highest probability among H/D/A
- Build 3×3 count matrix, compute percentages
- Same JOIN pattern as `/api/accuracy/scoped` for scoping

**Files modified:**
- `backend/main.py` — new endpoint
- `backend/models.py` — new response models

**Exit criteria:**
- [x] Endpoint returns 3×3 grid with counts and percentages
- [x] Scoping works for country, competition, team_id, source
- [x] Empty scope returns zeros gracefully

---

### Task 2: Backend — Team Search on Prediction History

**Role:** `/fullstack` | **Effort:** ~1.5h | **Priority:** P0

Add `search` query parameter to `GET /api/prediction-history`.

**Implementation:**
- Accept `search: str | None` parameter
- Split into whitespace-separated tokens
- For each token, add a WHERE clause: `(LOWER(home_team) LIKE '%token%' OR LOWER(away_team) LIKE '%token%')`
- All tokens must match (AND logic between tokens)
- Apply to both the count query and the items query

**SQL pattern:**
```sql
-- For search = "Liverpool United"
AND (LOWER(COALESCE(th1.name, th2.name)) LIKE '%liverpool%'
     OR LOWER(COALESCE(ta1.name, ta2.name)) LIKE '%liverpool%')
AND (LOWER(COALESCE(th1.name, th2.name)) LIKE '%united%'
     OR LOWER(COALESCE(ta1.name, ta2.name)) LIKE '%united%')
```

**Files modified:**
- `backend/main.py` — add `search` parameter to `/api/prediction-history`
- `src/live/prediction_tracker.py` — add `search` parameter to `get_prediction_history()`

**Exit criteria:**
- [x] `search=Liverpool` returns all Liverpool matches
- [x] `search=Liverpool United` returns matches where both tokens appear across home+away
- [x] Search is case-insensitive
- [x] Pagination works correctly with search (count reflects filtered total)
- [x] Empty search returns all results (backward compatible)

---

### Task 3: Backend — Scope prediction-accuracy Endpoint

**Role:** `/fullstack` | **Effort:** ~1h | **Priority:** P1

Add `country` and `team_id` filters to `GET /api/prediction-accuracy` so it can be called from any EloKit context.

**Files modified:**
- `backend/main.py` — add `country`, `team_id` parameters
- `src/live/prediction_tracker.py` — add `country`, `team_id` parameters to `get_prediction_accuracy()`

**Exit criteria:**
- [x] `/api/prediction-accuracy?country=England` returns England-scoped stats
- [x] `/api/prediction-accuracy?team_id=42` returns team-scoped stats
- [x] Existing `competition` and `source` filters still work
- [x] Backward compatible (no required new parameters)

---

### Task 4: Frontend — Detailed Accuracy View

**Role:** `/fullstack` | **Effort:** ~3h | **Priority:** P0

Replace the current "View all" inline expansion with navigation to a dedicated accuracy detail section. This section lives within the EloKit unified layout — it's shown when the user clicks "View details" on the accuracy widget.

**UI structure:**

The accuracy widget's "View all" link becomes "View details". Clicking it reveals a full-width detail panel below the accuracy card (or replaces the card content) containing:

1. **Summary row** — accuracy %, Brier score, total predictions, trend (already exists in compact form)
2. **Prediction Performance Grid** (Task 5)
3. **Per-competition breakdown table** (already exists in expanded view — move here)
4. **By-source breakdown** (already exists — move here)
5. **Match Prediction Log** with search (Task 6)

State management:
- `accuracyView: 'compact' | 'detail'` — toggles between summary card and full detail
- When in detail view, fetch grid + history data
- Back link to return to compact view

**Files modified:**
- `backend/templates/index.html` — new detail section, state management, fetch methods

**Exit criteria:**
- [x] "View details" link opens the detail panel
- [x] Back link returns to compact view
- [x] Detail view fetches grid and history data on open
- [x] All sections respect current navigation context (country/competition/team)

---

### Task 5: Frontend — Prediction Performance Grid Component

**Role:** `/fullstack` | **Effort:** ~2.5h | **Priority:** P0

Render the 3×3 outcome grid from Task 1's API data.

**Visual design:**
- Grid layout with clear "Predicted" header across top and "Actual" left label
- Column headers: Home, Draw, Away
- Row headers: Home, Draw, Away
- Each cell shows: count (large) + percentage (small, gray)
- Diagonal cells (correct predictions) have green background tint
- Off-diagonal cells have neutral/light red tint proportional to count
- Color intensity scales with `pct_of_total` (more matches = more saturated)
- Row totals on the right
- Grand total + accuracy % below the grid

**Responsive:**
- On mobile, cells stack or use abbreviated labels (H/D/A)

**Files modified:**
- `backend/templates/index.html` — grid HTML + Alpine.js rendering

**Exit criteria:**
- [x] 3×3 grid renders correctly with counts and percentages
- [x] Diagonal highlighted green, off-diagonal neutral
- [x] Color intensity scales with count
- [x] Row totals and grand total displayed
- [x] Responsive on mobile
- [x] Empty state handled (no predictions)

---

### Task 6: Frontend — Match Prediction Log

**Role:** `/fullstack` | **Effort:** ~3h | **Priority:** P0

Searchable, paginated match table within the detail view.

**Components:**

1. **Search bar**
   - Text input with search icon and placeholder: "Search teams..."
   - Debounced (300ms) — triggers API call after user stops typing
   - Resets to page 1 on new search
   - Clear button (x) when search has content

2. **Results count** — "Showing 1-20 of 3,456 predictions" (updates with search)

3. **Match table**
   - Columns: Date, Match (home vs away + score), Competition, Prediction (H/D/A probability bars), Result badge, Brier score
   - Prediction column: three mini-bars (home green, draw gray, away blue) with the predicted winner's bar highlighted/bold
   - Result: colored badge — H=green, D=amber, A=blue
   - Brier: colored text — gradient from green (0.0) through amber to red (1.0+)
   - Correct prediction: subtle checkmark or row highlight
   - Source badge: "Live" (green pill) or "Backfill" (gray pill)

4. **Pagination**
   - Previous / Next buttons (disabled at boundaries)
   - "Page X of Y" display
   - Stays on current page during search (resets to 1 on new search)

**Alpine.js state:**
```javascript
historySearch: '',
historyPage: 1,
historyPerPage: 20,
historyData: { items: [], total: 0, pages: 0 },
loadingHistory: false,
```

**Files modified:**
- `backend/templates/index.html` — table HTML, search input, pagination, fetch method

**Exit criteria:**
- [x] Table renders prediction history with all columns
- [x] Search filters by team name (multi-word across both teams)
- [x] Search is debounced (300ms)
- [x] Pagination works (prev/next, page X of Y)
- [x] Search resets to page 1
- [x] Loading state shown during fetch
- [x] Empty state: "No predictions found" when search has no results
- [x] Responsive: horizontal scroll on mobile, key columns visible

---

### Task 7: Tests

**Role:** `/test-runner` | **Effort:** ~2h | **Priority:** P1

**Test cases:**
- `/api/accuracy/grid` — returns correct 3×3 counts, percentages, accuracy
- `/api/accuracy/grid` — scoping by country, competition, team_id
- `/api/accuracy/grid` — empty scope returns zeros
- `/api/prediction-history?search=Liverpool` — returns Liverpool matches
- `/api/prediction-history?search=Liverpool+United` — multi-word search
- `/api/prediction-history?search=xyz` — no results returns empty items + total=0
- `/api/prediction-accuracy?country=England` — country scoping
- `/api/prediction-accuracy?team_id=42` — team scoping
- Regression: all existing tests pass (364+)

**Files modified:**
- `tests/test_backend.py` or new `tests/test_accuracy_detail.py`

**Exit criteria:**
- [x] All new tests pass (24 new tests)
- [x] Full suite: 388 tests passing, no regressions

---

## Task Dependencies

```
Task 1 (Grid API) ──────────────▶ Task 5 (Grid Frontend)
Task 2 (Search API) ────────────▶ Task 6 (Log Frontend)
Task 3 (Scope prediction-accuracy) ─▶ Task 4 (Detail View)

Task 4 (Detail View) ──▶ Task 5 (Grid in detail view)
Task 4 (Detail View) ──▶ Task 6 (Log in detail view)

Tasks 1-6 ──▶ Task 7 (Tests)
```

**Parallel tracks:**
- Tasks 1, 2, 3 are independent backend work (can run in parallel)
- Task 4 is the frontend shell — can start with mock data while APIs are built
- Tasks 5 and 6 slot into the detail view from Task 4
- Task 7 runs last after all features land

## Estimated Effort

| Task | Effort |
|------|--------|
| 1. Grid API endpoint | ~2h |
| 2. Team search on history | ~1.5h |
| 3. Scope prediction-accuracy | ~1h |
| 4. Detail view shell | ~3h |
| 5. Grid component | ~2.5h |
| 6. Match Prediction Log | ~3h |
| 7. Tests | ~2h |
| **Total** | **~15h** |

## Risks

1. **Search performance on 20K+ predictions**: SQLite `LIKE '%token%'` is not indexed. For 20K rows this should be fast enough (<100ms), but if it becomes slow, we can add a full-text search (FTS5) table. Mitigation: measure query time, add FTS only if >200ms.
2. **Grid accuracy vs widget accuracy**: The grid computes accuracy by counting "highest probability = actual outcome". This should match the existing `accuracy_pct` from `/api/accuracy/scoped`. Must verify they use the same logic.
3. **Draw prediction sparsity**: The model likely rarely predicts draws as the highest probability (Elo models assign ~25% max to draws). The "Predicted Draw" column may be very thin. This is a feature, not a bug — it reveals model behavior.

## Definition of Done

- [x] "View details" on accuracy widget opens detailed view
- [x] 3×3 Prediction Performance Grid renders with counts, percentages, color coding
- [x] Match Prediction Log displays with all columns
- [x] Team search works across both home and away names with multi-word queries
- [x] Pagination works on the match log
- [x] All views respect current EloKit navigation context (global/country/competition/team)
- [x] All tests passing (388 tests, 24 new, no regressions)
