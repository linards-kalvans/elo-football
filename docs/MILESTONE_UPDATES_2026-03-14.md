# Milestone Plan Updates — 2026-03-14

**Summary:** Three new milestones added based on product gaps identified during Sprint 7 review.

---

## New Milestones

### ✅ M8: Live Data & Fixtures (HIGH PRIORITY)

**Problem:** System currently operates on historical data only. Users need current predictions for upcoming matches.

**Solution:**
- Integrate live fixture API (API-Football, football-data.org, or similar)
- Auto-fetch upcoming fixtures daily
- Auto-update ratings when matches complete
- Display fixture predictions in frontend

**Impact:** Unlocks core product value — users can predict **this weekend's matches**, not just analyze history.

**Estimated effort:** 1 week (Sprint 9)

**Depends on:** Sprint 7 (frontend deployed)

**Blocks:** M9 (prediction tracking)

---

### ✅ M10: Initial Elo Calibration Fix (MEDIUM PRIORITY)

**Problem identified:**
```python
# src/elo_engine.py:161-163
init_rating = (
    s.initial_elo if season == first_season else s.promoted_elo
)
```

Current behavior:
- All teams in first season (2015) start at 1500
- Treats Bayern Munich and bottom-tier clubs as equals on day 0
- Incorrect because our dataset starts mid-history, not at "year 0" of football

**Root cause:**
- Dataset begins arbitrarily at 2015
- No context for which teams were already strong vs. weak in 2015

**Proposed solution: Warm-up period**
1. Ingest historical data back to 2010 (5 years before display window)
2. Run Elo algorithm from 2010-2026
3. **Display publicly only from 2015+**
4. By 2015, teams have realistic relative ratings without external dependencies

**Alternative considered:**
- Historical seeding (use 2015 UEFA coefficients) — rejected due to external data dependency
- Transfer learning (seed from ClubElo.com) — rejected due to external system dependency

**Impact:** Improves historical accuracy, making all predictions more trustworthy.

**Estimated effort:** 2 days (Sprint 10)

**Depends on:** M3 (pipeline capable of ingesting older data)

---

### ✅ M9: Prediction Tracking & Validation (MEDIUM PRIORITY)

**Problem:** Users can't see "what did we predict vs. what actually happened?"

**Solution:**
- Store every prediction made before matches
- Track actual outcomes
- Display prediction history ("We gave Arsenal 65% to win — they won 2-0")
- Dashboard showing model accuracy over time (Brier score, log-loss, calibration)

**Use cases:**
1. **Transparency:** "Here's our track record for last weekend's matches"
2. **Trust:** "Our model has 58% accuracy over the last month"
3. **Debugging:** "Model performance dropped last week — investigate"

**Impact:** Builds user trust and enables continuous model improvement.

**Estimated effort:** 4 days (Sprint 11)

**Depends on:** M8 (live data for actual outcomes)

---

## Updated Dependency Graph

```
M1-M3 (COMPLETED)
 │
 └──▶ M4 (Web App) [Sprint 7 IN PROGRESS]
       │
       ├──▶ M8 (Live Data) [NEW - Sprint 9 NEXT]
       │     └──▶ M9 (Prediction Tracking) [NEW - Sprint 11]
       │
       └──▶ M10 (Initial Elo Fix) [NEW - Sprint 10]
             └──▶ M5 (Parameter Optimization) [DEFERRED]

M6 (Full UEFA Coverage) [DEFERRED]
M7 (Two-Leg Ties) [DEFERRED]
M4.5 (Chart.js) [DEFERRED]
Sprint 8 (Tech Debt) [DEFERRED]
```

---

## Recommended Sprint Sequence

| Sprint | Focus | Duration | Status |
|--------|-------|----------|--------|
| Sprint 7 | Frontend + Deployment | 1 week | **IN PROGRESS** |
| **Sprint 9** | **M8: Live Data & Fixtures** | **1 week** | **NEXT** |
| **Sprint 10** | **M10: Initial Elo Calibration Fix** | **2 days** | **FOLLOW-UP** |
| Sprint 11 | M9: Prediction Tracking | 4 days | PLANNED |
| Sprint 12+ | M5, M6, M7, M4.5, S8 as needed | TBD | BACKLOG |

---

## ADR Decisions Needed

| Decision | Milestone | Options | Deadline |
|----------|-----------|---------|----------|
| **Live data API source** | M8 | API-Football ($0-50/mo), football-data.org (free), official APIs | Before Sprint 9 |
| **Initial rating calibration** | M10 | Warm-up period ✅ (recommended), historical seeding, transfer learning | Before Sprint 10 |

---

## Key Changes to Existing Milestones

### M5 (Parameter Optimization)
- **Was:** Next priority after M4
- **Now:** Deferred until after M8/M10
- **Reason:** Current parameters "good enough" (54% accuracy). Focus on data quality first.

### M6 (Full UEFA Coverage)
- **Was:** Expand to all 55 UEFA leagues
- **Now:** Deferred indefinitely
- **Reason:** 5 leagues + CL/EL sufficient for MVP. Add more leagues based on user demand.

### M7 (Two-Leg Ties)
- **Was:** Model knockout ties differently
- **Now:** Deferred indefinitely
- **Reason:** Current approach works. Not a user pain point.

---

## Rationale for Prioritization

### Why M8 (Live Data) is Priority #1:
1. **Core value prop:** "Predict this weekend's matches" >> "Analyze 2015 matches"
2. **User retention:** Historical analysis is one-time exploration; weekly predictions are recurring engagement
3. **Unblocks M9:** Can't track prediction accuracy without live outcomes

### Why M10 (Initial Elo Fix) is Priority #2:
1. **Data quality:** Improves trust in all predictions (past and future)
2. **Self-contained:** Doesn't require external APIs, lower risk
3. **Quick win:** 2-day effort, high impact on perceived accuracy

### Why M9 (Prediction Tracking) is Priority #3:
1. **Trust-building:** Shows users we track our own accuracy
2. **Transparency:** "Here's our track record" >> "Trust us"
3. **Product differentiation:** Many sites predict, few show historical accuracy

---

## Questions for Stakeholder

1. **Budget for live data API?**
   - Free tier only (~1000 requests/day)?
   - Or willing to pay $10-50/month for premium access?

2. **Acceptable data lag for "quasi-live"?**
   - Daily updates (fetch results once per day)?
   - Hourly updates (more API calls, higher cost)?
   - Real-time (requires websockets, significantly more complex)?

3. **Historical depth preference?**
   - 2010-2026 (16 seasons) sufficient for warm-up?
   - Or want deeper history (2005+, 21 seasons)?

4. **Prediction tracking must-have for launch?**
   - Can ship MVP without M9 and add later?
   - Or essential for credibility at launch?

---

## Impact on Current Sprint 7

**No changes required.** Sprint 7 continues as planned:
- Complete frontend (rankings, team detail, prediction widget)
- Deploy to Hetzner VPS
- M8/M9/M10 are post-deployment enhancements

---

## Files Updated

- ✅ `docs/milestones.md` — Added M8, M9, M10; updated dependency graph
- ✅ `docs/ROADMAP_PRIORITIES.md` — Detailed sequencing and rationale
- ✅ `docs/MILESTONE_UPDATES_2026-03-14.md` — This summary document
