# Sprint 8 — UI Enhancement & User Experience

**Depends on:** Sprint 7 completed (basic frontend deployed with ApexCharts)
**Status:** COMPLETED (2026-03-15)
**Goal:** Enhance the user experience with improved chart interactions, embedded comparisons in rankings, and rich team profile pages with fixture predictions.

**Priority:** HIGH — These improvements directly impact the core user experience and fulfill the product vision of an interactive, data-rich football Elo platform.

---

## Context

Sprint 7 delivered the foundation: rankings table, team detail pages with ApexCharts trajectories, multi-team comparison charts, and league context inheritance. Sprint 8 focuses on **UX polish and feature enrichment** to create a seamless, professional experience.

Three core improvements requested:

1. **Chart Performance Optimization** — Fix the "curves jumping" issue when adding/removing teams
2. **Embedded Comparison Charts** — Show mini comparison charts directly in rankings tables
3. **Rich Team Profile Pages** — Transform team pages into full profiles with fixtures, predictions, and historical context

---

## Items

### 1. Chart Performance Optimization

**Priority:** P1 | **Impact:** High (UX polish)

**Problem:**
Currently, when adding/removing teams in the comparison chart, all curves animate/jump because we call `chart.destroy()` and recreate the entire chart. This is visually distracting and slow.

**Root cause:**
```javascript
// In compare.html, when team added/removed:
removeTeam(teamId) {
    this.selectedTeams = this.selectedTeams.filter(t => t.id !== teamId);
    delete this.teamHistories[teamId];
    this.renderChart();  // ← Destroys and recreates entire chart
}

renderChart() {
    if (this.chart) {
        this.chart.destroy();  // ← All curves destroyed
    }
    this.chart = new ApexCharts(...);  // ← All curves re-created
    this.chart.render();  // ← All curves animate in
}
```

**Solution:**
Use ApexCharts' `updateSeries()` method instead of destroy/recreate:

```javascript
// Better approach:
addTeam(teamId, teamName) {
    // ... fetch data ...

    const newSeries = {
        name: teamName,
        data: historyData
    };

    if (this.chart) {
        // Append new series without destroying chart
        const allSeries = this.chart.w.config.series.concat([newSeries]);
        this.chart.updateSeries(allSeries);
    } else {
        this.renderChart();  // First time only
    }
}

removeTeam(teamId) {
    const teamIndex = this.selectedTeams.findIndex(t => t.id === teamId);
    this.selectedTeams = this.selectedTeams.filter(t => t.id !== teamId);
    delete this.teamHistories[teamId];

    if (this.chart) {
        // Update series array without destroying chart
        const newSeries = this.selectedTeams.map(team => ({
            name: team.name,
            data: this.teamHistories[team.id].map(h => ({
                x: new Date(h.date).getTime(),
                y: Math.round(h.rating)
            }))
        }));
        this.chart.updateSeries(newSeries, true);  // animate: true for smooth transition
    }
}
```

**Deliverables:**
- Refactor `addTeam()` to use `updateSeries()` instead of `renderChart()`
- Refactor `removeTeam()` to use `updateSeries()` instead of `renderChart()`
- Keep `renderChart()` for initial load only
- Test with rapid add/remove operations
- Verify slider still works correctly

**Acceptance criteria:**
- [ ] Adding a team animates only the new curve, existing curves stay static
- [ ] Removing a team animates only the removed curve, others stay static
- [ ] Multiple rapid add/remove operations work smoothly without visual glitches
- [ ] Time range slider continues to work correctly
- [ ] League selector continues to work correctly

**Files to modify:**
- `backend/templates/compare.html` (lines ~400-500, chart rendering logic)

**Estimated effort:** 2 hours

---

### 2. Embedded Comparison Charts in Rankings

**Priority:** P1 | **Impact:** High (UX, engagement)

**Vision:**
Transform the rankings table from a static list into an interactive data explorer. Show a **mini comparison chart** directly above the rankings table, allowing users to visualize the league's competitive landscape at a glance.

**Features:**

#### 2a. Default Mini Chart Above Rankings
- Show top 7 teams from the selected league as a mini comparison chart
- Chart updates automatically when league selector changes
- Compact height (~300px) to fit above the table without scrolling
- Same ApexCharts configuration as comparison page (smooth curves, legend hover highlighting)

#### 2b. Click Team → Add to Chart
- Clicking a team name in the rankings table **adds it to the chart** instead of navigating to team detail page
- Visual indicator: highlight the row in the table when team is in chart
- Chart expands/updates smoothly when new team added
- Max 10 teams in chart (same as comparison page limit)

#### 2c. Chart Controls
- **"View Full Comparison"** button → navigates to `/compare?teams={selected_ids}`
- **"Clear Chart"** button → removes all teams, resets to default top 7
- Team legend items clickable to remove teams (same as comparison page)

#### 2d. Team Detail Access
- Add a dedicated **"View Profile"** icon/button in each table row
- Small icon (e.g., 📊 or info icon) next to team name
- Clicking icon navigates to `/team/{id}?league={code}`
- Preserves team name clickability for chart interaction

**Implementation approach:**

1. **Reuse comparison chart component**
   - Extract chart rendering logic from `compare.html` into shared Alpine.js component
   - Import same component in `rankings.html`

2. **Table row interaction**
   ```html
   <tr @click="addTeamToChart(team.team_id, team.team)"
       :class="{ 'bg-indigo-50': chartTeams.includes(team.team_id) }">
       <td>{{ team.rank }}</td>
       <td class="flex items-center gap-2">
           <button @click.stop="navigateToTeam(team.team_id)"
                   class="text-gray-400 hover:text-indigo-600">
               📊
           </button>
           <span>{{ team.team }}</span>
       </td>
       <td>{{ team.rating }}</td>
   </tr>
   ```

3. **Chart state management**
   ```javascript
   Alpine.data('rankingsPage', () => ({
       chartTeams: [],  // Array of team IDs in chart
       chartData: {},   // Team histories for chart

       addTeamToChart(teamId, teamName) {
           if (this.chartTeams.length >= 10) {
               alert('Maximum 10 teams in chart');
               return;
           }
           if (!this.chartTeams.includes(teamId)) {
               this.chartTeams.push(teamId);
               this.loadTeamHistory(teamId, teamName);
           }
       },

       removeTeamFromChart(teamId) {
           this.chartTeams = this.chartTeams.filter(id => id !== teamId);
           delete this.chartData[teamId];
           this.updateChart();
       }
   }));
   ```

**Deliverables:**
- Mini comparison chart embedded in `rankings.html` above the table
- Chart shows top 7 teams by default for selected league
- Clicking team name in table adds it to chart
- Chart updates smoothly without full page reload
- "View Profile" button/icon for team detail navigation
- "View Full Comparison" button linking to `/compare?teams={ids}`
- Visual indicators for teams currently in chart (highlighted rows)

**Acceptance criteria:**
- [ ] Mini chart displays top 7 teams on page load
- [ ] Chart updates when league selector changes
- [ ] Clicking team in table adds it to chart (max 10 teams)
- [ ] Chart legend allows removing teams
- [ ] Rows visually indicate which teams are in chart
- [ ] "View Profile" button navigates to team detail page
- [ ] "View Full Comparison" button navigates to comparison page with current teams
- [ ] Mobile responsive (chart scrollable on small screens)

**Files to modify:**
- `backend/templates/rankings.html` (add chart component, update table interaction)
- Possibly extract shared chart component to `backend/static/js/chart-component.js`

**Estimated effort:** 6 hours

---

### 3. Rich Team Profile Pages

**Priority:** P1 | **Impact:** High (feature completeness)

**Vision:**
Transform the team detail page from a simple chart into a comprehensive team profile with historical trajectory, upcoming fixtures with predictions, and recent results with prediction accuracy.

**Features:**

#### 3a. Upcoming Fixtures with Predictions

**Display:**
- Table of upcoming fixtures for the team (next 5-10 matches)
- Columns: Date, Opponent, Venue (H/A/N), Competition, Predicted Result
- Predicted result shown as probability bars (Win/Draw/Loss %)
- Click fixture → expand to show detailed prediction breakdown

**Data source:**
- **Short-term (Sprint 8):** Mock fixture data for demonstration
  - Fetch from SQLite: next opponents based on typical league schedule
  - Use current Elo ratings to generate predictions
  - Mark fixtures as "Upcoming" with estimated dates

- **Long-term (M8):** Real fixture data from live API
  - Replace mock data with actual scheduled matches
  - Real kickoff times and venues

**API endpoint (new):**
```python
@app.get("/api/teams/{team_id}/fixtures", tags=["Teams"])
async def get_team_fixtures(
    team_id: int,
    upcoming: int = Query(5, description="Number of upcoming fixtures"),
):
    """Return upcoming fixtures for a team with win probability predictions."""
    # For Sprint 8: Generate mock fixtures based on league schedule
    # For M8: Fetch real fixtures from external API
    return {
        "team_id": team_id,
        "team_name": "Arsenal",
        "fixtures": [
            {
                "date": "2026-03-20",
                "opponent_id": 42,
                "opponent": "Chelsea",
                "venue": "H",
                "competition": "Premier League",
                "prediction": {
                    "home_win": 0.52,
                    "draw": 0.28,
                    "away_win": 0.20,
                    "elo_home": 1835.7,
                    "elo_away": 1693.5
                }
            },
            # ... more fixtures
        ]
    }
```

**UI mockup:**
```
┌─────────────────────────────────────────────────────────┐
│ Upcoming Fixtures                                       │
├─────────────────────────────────────────────────────────┤
│ Date       Opponent      Venue  Competition   Prediction│
│ Mar 20     Chelsea       Home   EPL          █████░ 52% │
│                                              ███░░░ 28% │
│                                              ██░░░░ 20% │
│ Mar 27     Man City      Away   EPL          ██░░░░ 23% │
│ Apr 3      Bayern Munich Home   CL           ████░░ 45% │
└─────────────────────────────────────────────────────────┘
```

#### 3b. Recent Results with Prediction Accuracy

**Display:**
- Table of last 5-10 matches
- Columns: Date, Opponent, Venue, Result (score), Predicted vs Actual
- Color-coded accuracy: green if prediction correct, amber if close, red if wrong
- Show Elo change from the match

**Data source:**
- Fetch recent matches from `matches` table
- Fetch pre-match Elo ratings from `ratings_history`
- Generate predictions based on those historical ratings
- Compare prediction to actual result

**API endpoint (new):**
```python
@app.get("/api/teams/{team_id}/results", tags=["Teams"])
async def get_team_results(
    team_id: int,
    limit: int = Query(10, description="Number of recent results"),
):
    """Return recent results with predictions and Elo changes."""
    return {
        "team_id": team_id,
        "team_name": "Arsenal",
        "results": [
            {
                "date": "2026-03-10",
                "opponent_id": 17,
                "opponent": "Liverpool",
                "venue": "A",
                "score_for": 2,
                "score_against": 1,
                "result": "W",  # W/D/L
                "prediction": {
                    "home_win": 0.55,  # Opponent was home
                    "draw": 0.27,
                    "away_win": 0.18,  # Arsenal away
                },
                "predicted_result": "L",  # Most likely outcome
                "prediction_correct": False,  # Arsenal won but predicted to lose
                "elo_before": 1828.3,
                "elo_after": 1835.7,
                "elo_change": +7.4
            },
            # ... more results
        ]
    }
```

**UI mockup:**
```
┌─────────────────────────────────────────────────────────┐
│ Recent Results                                          │
├─────────────────────────────────────────────────────────┤
│ Date    Opponent    Result  Predicted  Elo Change      │
│ Mar 10  Liverpool   2-1 W   L (18%)    +7.4 ▲          │
│         (Away)              🔴 Upset win               │
│ Mar 3   Aston Villa 3-0 W   W (65%)    +4.2 ▲          │
│         (Home)              🟢 As expected             │
│ Feb 24  Man City    1-1 D   L (25%)    +2.1 ▲          │
│         (Away)              🟡 Better than expected    │
└─────────────────────────────────────────────────────────┘
```

#### 3c. Team Statistics Summary

**Display (top of page, before chart):**
- Current Elo rating + rank
- League position (if available)
- Recent form: W/D/L over last 5 matches
- Elo trend: ↑ or ↓ over last 30 days
- Best and worst Elo rating in history (with dates)

**UI mockup:**
```
┌─────────────────────────────────────────────────────────┐
│ Arsenal                                                 │
│ 🏴󠁧󠁢󠁥󠁮󠁧󠁿 England · Premier League                              │
├─────────────────────────────────────────────────────────┤
│ Current Elo: 1835.7 (#2 worldwide, #1 in EPL)          │
│ Recent Form: W-W-D-L-W (12 pts from last 5)            │
│ Trend: ↑ +15.2 over last 30 days                       │
│ Peak: 1842.3 (Feb 2026) · Lowest: 1234.5 (Aug 2016)    │
└─────────────────────────────────────────────────────────┘
```

#### 3d. Enhanced Chart with Annotations

**Additions to existing ApexCharts trajectory:**
- **Match result markers**: Small dots on the curve for major wins/losses
  - Green dot = major win (>10 Elo gain)
  - Red dot = major loss (>10 Elo drop)
  - Click dot → show match details tooltip
- **Competition highlights**: Shaded regions for CL campaigns
  - Light overlay for months when team was in CL knockout rounds
- **Season dividers**: Vertical lines marking season boundaries
  - Helps contextualize rating changes across seasons

**ApexCharts annotations:**
```javascript
annotations: {
    points: [
        {
            x: new Date('2025-05-15').getTime(),
            y: 1842,
            marker: {
                size: 6,
                fillColor: '#10b981',  // Green for big win
            },
            label: {
                text: 'CL Final Win vs Bayern'
            }
        },
        // ... more key matches
    ],
    xaxis: [
        {
            x: new Date('2025-07-01').getTime(),
            borderColor: '#d1d5db',
            label: { text: '2025/26' }
        },
        // ... season boundaries
    ]
}
```

**Deliverables:**
- Team statistics summary card at top of team detail page
- Upcoming fixtures table with predictions (mock data for Sprint 8)
- Recent results table with prediction accuracy
- Enhanced chart with match annotations and season markers
- Two new API endpoints: `/api/teams/{id}/fixtures` and `/api/teams/{id}/results`
- Responsive layout on mobile

**Acceptance criteria:**
- [ ] Statistics summary shows current Elo, rank, form, and trend
- [ ] Upcoming fixtures table displays next 5 matches with predictions
- [ ] Recent results table shows last 10 matches with prediction accuracy
- [ ] Chart includes annotations for major wins/losses
- [ ] Chart includes season boundary markers
- [ ] Color-coded accuracy indicators (green/amber/red)
- [ ] Mobile responsive layout
- [ ] All data fetched from new API endpoints
- [ ] Mock fixture data realistic (actual league opponents, reasonable dates)

**Files to modify:**
- `backend/templates/team.html` (add fixtures, results, statistics sections)
- `backend/main.py` (add `/api/teams/{id}/fixtures` and `/api/teams/{id}/results` endpoints)
- Possibly `backend/static/css/team-profile.css` for custom styling

**Estimated effort:** 10 hours

---

## Out of Scope (Deferred)

- **Real fixture data** — M8 (Live Data & Fixtures) will add real API integration. Sprint 8 uses mock data.
- **Match detail pages** — Each match gets its own page with lineups, events, etc. (Future milestone)
- **Head-to-head comparison** — Dedicated H2H page showing all historical matches between two teams (M4.5 or later)
- **Player-level data** — Squad rosters, player ratings, transfers (Out of scope for MVP)
- **Social features** — User accounts, saved teams, prediction leagues (Out of scope for MVP)

---

## Dependencies

- Sprint 7 complete (ApexCharts migration, league context, comparison charts)
- `/tmp/future_chart_optimization.md` (tracked issue from Sprint 7)
- `/tmp/league_context_fix_summary.md` (reference for league inheritance patterns)

---

## Acceptance Criteria (Sprint 8 Complete)

### Chart Performance
- [ ] Adding/removing teams in comparison chart updates smoothly without full re-render
- [ ] Only new/removed curves animate, existing curves stay static
- [ ] Slider and league selector continue to work correctly

### Rankings Embedded Chart
- [ ] Mini comparison chart visible above rankings table
- [ ] Chart shows top 7 teams by default for selected league
- [ ] Clicking team name in table adds it to chart
- [ ] Chart legend allows removing teams
- [ ] "View Full Comparison" button navigates to `/compare` with selected teams
- [ ] "View Profile" icon/button navigates to team detail page
- [ ] Visual indicators (highlighted rows) for teams in chart

### Team Profile Page
- [ ] Statistics summary shows current rating, rank, form, and trend
- [ ] Upcoming fixtures table displays next 5 matches with predictions
- [ ] Recent results table shows last 10 matches with prediction accuracy
- [ ] Chart includes annotations for major wins/losses and season boundaries
- [ ] Color-coded prediction accuracy (green/amber/red)
- [ ] Two new API endpoints (`/fixtures` and `/results`) working
- [ ] Mock fixture data realistic and useful for demonstration

### Cross-cutting
- [ ] All new features responsive on mobile
- [ ] No performance degradation on page load times
- [ ] All existing features continue to work (no regressions)
- [ ] Code follows project patterns (Alpine.js, Tailwind, ApexCharts)

---

## Testing Strategy

### Unit Tests (Backend)
- [ ] Test `/api/teams/{id}/fixtures` endpoint with mock data
- [ ] Test `/api/teams/{id}/results` endpoint with historical data
- [ ] Test prediction calculation for fixtures
- [ ] Test Elo change calculation for results

### Integration Tests (Frontend)
- [ ] Test chart update performance (measure render time before/after optimization)
- [ ] Test rankings chart interaction (add/remove teams, navigation)
- [ ] Test team profile page renders all sections correctly
- [ ] Test prediction accuracy calculation correctness

### Manual Testing
- [ ] Rapid add/remove teams in comparison chart (no visual glitches)
- [ ] Click teams in rankings table → chart updates smoothly
- [ ] Navigate between rankings → team profile → comparison pages
- [ ] Verify predictions look realistic and sum to 100%
- [ ] Test on mobile device (chart scrolling, responsive tables)

---

## Task Breakdown

| Task | Owner | Est. Hours | Priority |
|------|-------|------------|----------|
| 1. Chart performance optimization | `/fullstack` | 2h | P1 |
| 2a. Extract shared chart component | `/fullstack` | 2h | P1 |
| 2b. Embed chart in rankings page | `/fullstack` | 2h | P1 |
| 2c. Add table row interaction | `/fullstack` | 2h | P1 |
| 3a. Create fixtures API endpoint (mock) | `/fullstack` | 2h | P1 |
| 3b. Create results API endpoint | `/fullstack` | 2h | P1 |
| 3c. Add statistics summary section | `/fullstack` | 2h | P1 |
| 3d. Add fixtures table to team page | `/fullstack` | 2h | P1 |
| 3e. Add results table to team page | `/fullstack` | 2h | P1 |
| 3f. Add chart annotations | `/fullstack` | 2h | P1 |
| Testing & bug fixes | `/devops` | 3h | P1 |
| Documentation updates | `/tech-writer` | 1h | P2 |

**Total estimated effort:** 24 hours (~3 full working days)

---

## Success Metrics

**UX Improvements:**
- Chart interaction feels instant (< 200ms to add/remove team)
- Users can explore league rankings visually without leaving the page
- Team profiles provide comprehensive context at a glance

**Technical Metrics:**
- Chart update time reduced by 80% (from ~1s to ~200ms)
- Zero full page reloads for chart interactions
- API response times < 100ms for fixtures/results endpoints

**User Value:**
- Rankings page becomes an interactive data explorer, not just a static table
- Team profiles provide actionable insights (upcoming match predictions)
- Prediction accuracy tracking builds trust in the model

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Chart optimization breaks existing functionality | High | Comprehensive testing of slider, league selector, and URL params |
| Embedded chart slows down rankings page load | Medium | Lazy-load chart after table renders; use lightweight default (top 7 only) |
| Mock fixture data looks unrealistic | Low | Use real league schedules and rotate opponents to simulate realistic fixtures |
| Prediction accuracy calculation incorrect | High | Unit tests comparing predicted vs actual results; validate math carefully |

---

## Next Steps After Sprint 8

**Sprint 9: Technical Debt & Optimization**
- Fix Pydantic deprecation warnings (54 warnings in `backend/models.py`)
- Optimize tier weights via parameter sweep (currently hand-picked)
- Increase test coverage for edge cases
- Performance profiling and database query optimization

**M8: Live Data & Fixtures** (High Priority)
- Replace mock fixtures with real API data
- Automated data refresh pipeline
- Real-time prediction tracking
