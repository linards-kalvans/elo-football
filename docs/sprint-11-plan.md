# Sprint 11 Plan — Dockerized Cron & Prediction Dashboard

> Status: COMPLETED (2026-03-16)
> Depends on: Sprint 10 (completed)
> Milestones: M8 (final), M9 (frontend)

## Goals

1. **Dockerized daily update cron** — Bake the 2x daily update schedule into the Docker image so production stays fresh without manual cron setup on the VPS
2. **Prediction accuracy dashboard** — Frontend page showing model performance: Brier scores, calibration chart, per-competition breakdown
3. **Prediction history page** — "Last weekend's predictions" — show past predictions alongside actual results

## Tasks

### Task 1: Dockerized Cron for Daily Updates ✅
**Role:** `/devops` | **Effort:** ~4h | **Priority:** P0

The `scripts/run_daily_update.py` exists and works, but requires a manual cron entry on the VPS host. Bake it into the container so updates run automatically.

**Approach:** Lightweight Python sleep-loop scheduler (`scripts/cron_runner.py`) running as a Docker Compose sidecar service — no external cron dependencies.

**Deliverables:**
- `cron` service in `docker-compose.yml` sharing the same image and data volume
- `scripts/cron_runner.py`: checks every 5 min, runs at 06:00 and 18:00 UTC
- `FOOTBALL_DATA_API_KEY` env var passed through to both app and cron containers
- Cron container restarts on failure (`restart: unless-stopped`)
- `scripts/` directory copied into Docker image

**Exit criteria:**
- [x] `docker compose up` starts both web server and cron scheduler
- [x] Daily update runs automatically at configured times
- [x] Cron logs are visible via `docker compose logs cron`
- [x] API key and DB path correctly shared between services

---

### Task 2: Prediction History API Endpoint ✅
**Role:** `/fullstack` | **Effort:** ~3h | **Priority:** P1

Backend endpoint returning past predictions with actual outcomes — the data layer for the prediction history page.

**Deliverables:**
- `GET /api/prediction-history` endpoint with pagination, competition filter, date range filters
- `get_prediction_history()` in `src/live/prediction_tracker.py`
- `PredictionHistoryItem` and `PredictionHistoryResponse` Pydantic models
- `GET /prediction-history` page route

**Exit criteria:**
- [x] Endpoint returns paginated prediction history with actual outcomes
- [x] Filters by competition and date range work
- [x] Response includes team names, predicted probabilities, and actual results

---

### Task 3: Prediction History Frontend Page ✅
**Role:** `/fullstack` | **Effort:** ~4h | **Priority:** P1

User-facing page showing what the model predicted and what actually happened.

**Deliverables:**
- `backend/templates/prediction_history.html` with Alpine.js
- Table: Date | Match | Predicted (probability bars) | Actual Result | Brier Score
- Color coding: green for good predictions (low Brier), red for poor ones
- Competition filter dropdown, date range inputs
- Pagination controls
- Summary stats cards (total scored, mean Brier, recent form)
- Empty state message when no scored predictions exist

**Exit criteria:**
- [x] Page at `/prediction-history` shows scored predictions
- [x] Probability bars visually show predicted outcomes vs actual
- [x] Filter by competition works
- [x] Pagination works for large datasets

---

### Task 4: Prediction Accuracy Dashboard ✅
**Role:** `/fullstack` | **Effort:** ~5h | **Priority:** P1

Frontend page visualizing model performance — the "how good is our model?" page.

**Deliverables:**
- `backend/templates/accuracy.html` with Alpine.js + ApexCharts
- Calibration chart: predicted vs actual frequency with diagonal reference
- Brier score trend: rolling 50-prediction average line chart with random baseline annotation
- Per-competition accuracy table sorted best to worst
- Summary cards: total predictions, mean Brier, median Brier, recent form

**New/modified API:**
- Extended `/api/prediction-accuracy` response with `time_series` field
- `_compute_brier_time_series()` helper in `src/live/prediction_tracker.py`
- `BrierTimeSeriesPoint` Pydantic model

**Exit criteria:**
- [x] Calibration chart renders correctly with diagonal reference line
- [x] Brier score trend chart shows rolling performance over time
- [x] Per-competition breakdown table displayed
- [x] Summary cards show key metrics at a glance
- [x] Page accessible from nav bar

---

### Task 5: Navigation & Integration ✅
**Role:** `/fullstack` | **Effort:** ~1h | **Priority:** P2

**Deliverables:**
- "History" and "Accuracy" links added to nav bar in `base.html`
- Cross-link from accuracy dashboard to prediction history
- FastAPI route registrations in `backend/main.py`

**Exit criteria:**
- [x] All new pages reachable from nav bar
- [x] Cross-navigation between prediction-related pages works

---

### Task 6: Tests ✅
**Role:** `/test-runner` | **Effort:** ~2h | **Priority:** P2

**Exit criteria:**
- [x] No regressions — all 363 tests passing
- [x] New endpoints return correct response structure

## Task Dependencies

```
Task 1 (Dockerized Cron) — independent ✅

Task 2 (Prediction History API) ──▶ Task 3 (Prediction History Frontend) ✅
                                 ──▶ Task 5 (Navigation) ✅

Task 4 (Accuracy Dashboard) ──▶ Task 5 (Navigation) ✅

Task 6 (Tests) — runs after Tasks 1-4 ✅
```

## Out of Scope

- **Historical prediction backfill** — pages are empty until live predictions accumulate or backfill runs (deferred to Sprint 12, M9b)
- Confidence intervals on predictions (M9 future)
- Performance degradation alerts (M9 future)
- Shareable chart configurations (M4.5)
- UI redesign (M11, Sprint 12)
- Chart export PNG/CSV (M4.5, Sprint 13)

## Results

**Completed:** 2026-03-16 | **Tests:** 363 passing | **0 regressions**

### New Files
- `scripts/cron_runner.py` — lightweight sleep-loop cron scheduler
- `backend/templates/prediction_history.html` — prediction history page
- `backend/templates/accuracy.html` — accuracy dashboard with ApexCharts

### Modified Files
- `docker-compose.yml` — added `cron` sidecar service
- `Dockerfile` — added `COPY scripts/ scripts/`
- `backend/main.py` — 3 new routes (`/prediction-history`, `/accuracy`, `/api/prediction-history`)
- `backend/models.py` — 4 new Pydantic models
- `src/live/prediction_tracker.py` — `get_prediction_history()`, `_compute_brier_time_series()`
- `backend/templates/base.html` — nav bar updated with History and Accuracy links

### Known Limitation
Pages display empty state messages because no historical predictions have been backfilled. This is tracked as M9b (Historical Prediction Backfill) and scoped for Sprint 12.

## Definition of Done

- [x] `docker compose up` runs web server + automated daily updates with zero VPS-side configuration
- [x] Prediction history page shows past predictions with outcomes (empty state when no data)
- [x] Accuracy dashboard shows calibration chart, Brier trend, and per-competition stats (empty state when no data)
- [x] All new pages linked from navigation
- [x] Tests passing, no regressions
- [x] M8 fully complete (dockerized cron was the last exit criterion)
