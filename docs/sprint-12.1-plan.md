# Sprint 12.1 Plan — EloKit Polish & Bug Fixes

> Status: COMPLETED
> Depends on: Sprint 12 (completed)
> Milestones: M11 (UI Redesign — polish)

## Goals

Fix critical data-loading regression from Sprint 12 polish changes, implement proper "Load more" UX for fixtures, add chart team management (add/remove teams) with zoom controls, and polish rankings display.

## Completed Tasks

### Task 1: Fix Data Loading Regression ✅
**Priority:** P0 (BLOCKER)

- **Root cause:** Nested `<button>` inside `<button>` in fixtures header — invalid HTML causing browsers to break DOM tree, moving sections outside the `eloPage()` Alpine.js `x-data` scope.
- **Fix:** Replaced nested `<button>` with `<div>` using `@click` for collapse toggle.
- **Additional fix:** Removed nested `x-data` in chart team controls — moved `teamQuery`, `teamResults`, `showTeamSearch` state into `eloPage()` component.

### Task 2: Fixtures — Collapsible with "Load More" Pagination ✅
**Priority:** P1

- Default: 3 finished + 3 upcoming fixtures (collapsible section)
- "Load more..." link at top loads older finished matches (prepends)
- "Load more..." link at bottom loads more upcoming matches (appends)
- Team context shows fixtures from ALL competitions (not just domestic league)
- Backend: added `offset_finished`, `offset_upcoming` params + `has_more_finished`, `has_more_upcoming` to `ScopedFixturesResponse`

**Files modified:**
- `backend/main.py` — pagination params, offset/limit SQL
- `backend/models.py` — `has_more_finished`, `has_more_upcoming` fields
- `backend/templates/index.html` — fixtures section

### Task 3: Rankings — Top 5 + Team Context ✅
**Priority:** P1

- Fetches full rankings, displays top 5 by default
- Team context: top 5 + selected team ±3 (with visual gap separator)
- "View all" / "Show less" toggle expands to full table
- Team row highlighted with `bg-brand-50`

### Task 4: Chart — Team Add/Remove & Zoom ✅
**Priority:** P1

- Zoom/pan/reset toolbar enabled via ApexCharts config
- Team chips below chart with X to remove
- "+ Add team" button opens search input with results dropdown
- **Key fix:** Dropdown opens upward (`bottom-full`) to avoid overflow clipping
- **Key fix:** Uses `chart.updateOptions()` for add/remove instead of destroy/recreate — avoids DOM timing conflicts with Alpine.js
- Section uses `overflow-visible` to prevent dropdown clipping

### Task 5: Header Banner Inline ✅
**Priority:** P2

- "Club Rating Analytics" centered between logo and search in header flex row
- Hidden on mobile (space constrained)

### Task 6: Tests ✅
**Priority:** P2

- 360/360 tests passing, no regressions

## Files Modified

| File | Changes |
|------|---------|
| `backend/templates/index.html` | Full rewrite: fixtures collapse + pagination, chart controls, rankings top-5 logic |
| `backend/templates/base.html` | Banner text inline in header |
| `backend/main.py` | Fixtures API: `offset_finished`, `offset_upcoming` params, `LIMIT ? OFFSET ?` SQL |
| `backend/models.py` | `has_more_finished`, `has_more_upcoming` fields on `ScopedFixturesResponse` |

## Definition of Done

- [x] All 4 data sections load and display correctly at all context levels
- [x] Fixtures show 3+3 by default with "Load more..." pagination
- [x] Rankings show top 5 + team context with "View all" to expand
- [x] Chart has zoom controls and team add/remove functionality
- [x] Banner text inline with logo
- [x] All 360 tests passing
