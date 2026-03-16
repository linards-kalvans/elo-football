# Roadmap Priorities — Post-Sprint 7

**Last updated:** 2026-03-14
**Current status:** Sprint 7 in progress (frontend + deployment)

---

## Immediate Next Steps (After Sprint 7)

### Priority 1: M8 — Live Data & Fixtures 🔥

**Why now:**
- Fundamental to product value — users want current predictions, not just historical analysis
- Unblocks prediction tracking (M9)
- Required before any public launch

**What's needed:**
1. **Data source selection ADR** (Estimated: 4 hours research + 2 hours ADR)
   - Compare API-Football, football-data.org, official APIs
   - Evaluate: cost, rate limits, coverage (all 5 leagues + CL/EL), reliability, data quality
   - Recommendation: Start with free tier, upgrade if needed

2. **Fixtures ingestion** (Estimated: 8 hours)
   - Add `fixtures` table to database schema
   - Scheduled fetch script (daily cron job)
   - Display upcoming matches in frontend with predictions

3. **Result auto-update** (Estimated: 6 hours)
   - Fetch completed match results (post-matchday)
   - Incremental rating updates (don't recompute full history)
   - Validation: final score confirmed, not abandoned/postponed

**Sprint scope:** Sprint 9 (1 week)

**Exit criteria:**
- Fixtures displayed in frontend 7 days ahead
- Ratings update automatically within 24 hours of match completion
- API costs acceptable for production (<$20/month)

---

### Priority 2: M10 — Initial Elo Calibration Fix ⚠️

**Why now:**
- Impacts data quality and user trust (top clubs shouldn't start at 1500 in 2015)
- Relatively self-contained fix, doesn't require external APIs
- Improves historical accuracy, which affects all predictions

**What's needed:**
1. **Ingest historical data back to 2010** (Estimated: 3 hours)
   - Fetch 2010-2014 data from Football-Data.co.uk
   - Ingest into pipeline (same sources already working)

2. **Implement warm-up period** (Estimated: 4 hours)
   - Run Elo from 2010, display from 2015
   - Add `display_from_date` config parameter
   - Validate 2015 starting ratings reasonable

3. **Write ADR** (Estimated: 1 hour)
   - Document warm-up approach and rationale
   - Compare to alternative approaches (historical seeding, transfer learning)

**Sprint scope:** Sprint 10 (2 days)

**Exit criteria:**
- All teams have contextually appropriate 2015 starting ratings
- Bayern/Barcelona/Real Madrid ~1700-1850 in 2015
- Bottom-tier teams ~1300-1450 in 2015
- ADR documented

---

### Priority 3: M9 — Prediction Tracking 📊 **[MUST-HAVE FOR LAUNCH]**

**Why critical:**
- **Stakeholder requirement:** Must complete before public launch
- Builds trust and credibility from day 1
- Differentiates from competitors who don't show their accuracy

**What's needed:**
1. **Predictions table** (Estimated: 2 hours)
   - Store predictions before matches (match_id, p_home, p_draw, p_away, timestamp)

2. **Outcome tracking** (Estimated: 4 hours)
   - Link predictions to actual results
   - Calculate accuracy metrics (Brier score, log-loss)

3. **Frontend display** (Estimated: 6 hours)
   - "Recent predictions" page showing last week's predictions vs. outcomes
   - Accuracy badge on prediction widget ("Our model: 58% accurate this month")

**Sprint scope:** Sprint 11 (4 days)

**Exit criteria:**
- All predictions stored before matches
- User can see "what we predicted vs. what happened" for past week
- Accuracy badge displayed prominently

---

## Lower Priority (Defer Until After M8-M10)

### M5: Advanced Parameter Optimization
- **Why defer:** Current parameters are "good enough" (54% accuracy)
- **Revisit when:** After M8/M10 improve data quality, then optimize

### M6: Full UEFA League Coverage
- **Why defer:** 5 leagues + CL/EL/Conference is sufficient for MVP
- **Revisit when:** User demand exceeds current coverage

### M7: Two-Leg Tie Modeling
- **Why defer:** Current approach works, not causing user complaints
- **Revisit when:** CL knockout prediction accuracy becomes a priority

### M4.5: Chart.js Enhancements
- **Why defer:** Basic charts sufficient for MVP
- **Revisit when:** User feedback requests zoom/pan/multi-team features

### Sprint 8: Technical Debt
- **Why defer:** No blocking issues, Pydantic warnings non-critical
- **Revisit when:** Between major milestones, or if test coverage drops

---

## Recommended Sequence

```
Sprint 7:  Frontend + Deployment [IN PROGRESS]
           └─▶ Deploy MVP to Hetzner VPS (PRIVATE BETA)

Sprint 9:  M8 — Live Data & Fixtures [NEXT - 1 week]
           ├─ Data source: football-data.org (free tier, 10 calls/min)
           ├─ Fixtures ingestion (daily cron)
           └─ Auto-update pipeline

Sprint 10: M10 — Initial Elo Fix [2 days]
           ├─ Ingest 2010-2014 data
           ├─ Warm-up period implementation
           └─ Validate 2015 starting ratings

Sprint 11: M9 — Prediction Tracking [MUST COMPLETE - 4 days]
           ├─ Predictions storage
           ├─ Accuracy metrics
           └─ Frontend display

           🚀 PUBLIC LAUNCH GATE 🚀
           ↓ (Only after M8 + M9 + M10 complete)

Sprint 12+: Post-Launch Iteration
           ├─ M5 (Parameter Optimization - if accuracy <52%)
           ├─ M4.5 (Chart.js enhancements - based on user feedback)
           ├─ Sprint 8 (Tech debt cleanup)
           └─ M6, M7 (as needed)
```

---

## Key Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Live API costs too high | High | Start with free tier, monitor usage, add caching |
| Live API unreliable | Medium | Implement fallback source, degrade gracefully |
| Historical data (2010-2014) unavailable | Medium | Use external Elo ratings for seeding if needed |
| User traffic exceeds Hetzner VPS capacity | Low | Monitor, upgrade tier or add load balancer |

---

## Success Metrics (Post-M8/M10)

- **Data freshness**: Fixtures updated daily, results within 24h
- **Prediction accuracy**: Brier score < 0.25 (industry standard)
- **Rating calibration**: Top teams 1700-1900, bottom 1300-1500
- **User engagement**: TBD after launch (track page views, prediction usage)

---

## Stakeholder Decisions (2026-03-14)

1. **Budget for live data API:** ✅ **DECIDED**
   - **Preference:** Free tier
   - **Maximum:** €20/month if needed
   - **Action:** Start with free tier (football-data.org 10 calls/min), upgrade if limits hit

2. **Historical data depth:** ✅ **DECIDED**
   - **Scope:** 2010-2026 (16 seasons)
   - **Rationale:** Sufficient warm-up period for initial Elo calibration

3. **Prediction tracking priority:** ✅ **DECIDED — MUST-HAVE FOR LAUNCH**
   - **Requirement:** Complete M9 before public launch
   - **Rationale:** Credibility and transparency essential from day 1

4. **Data freshness:** ✅ **DECIDED**
   - **Frequency:** Daily updates
   - **Schedule:** Fetch fixtures/results once per day (post-matchday)
