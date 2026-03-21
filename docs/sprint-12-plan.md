# Sprint 12 Plan — EloKit Redesign

> Status: COMPLETED
> Depends on: Sprint 11 (completed)
> Milestones: M11 (UI Redesign)
> Design spec: `docs/sprint-12-design-spec.md`
> Wireframe: `docs/wireframes/EloKit Wireframe-Page 1.png`

## Goals

Replace the current multi-page layout (separate rankings, compare, predict, fixtures, accuracy, prediction-history pages) with a **single unified layout** branded "EloKit". All contexts (global, nation, league, team) share the same page structure: fixtures → accuracy widget → Elo chart → rankings table, with content scoped to the navigation context.

## Architecture Decisions

### URL Scheme
```
/                                    → Global (all teams, all competitions)
/england                             → Nation (all English teams)
/england/premier-league              → League (PL teams)
/england/premier-league/liverpool    → Team (single team)
```
A single FastAPI route with optional path segments, resolved to a Jinja2 template with Alpine.js fetching scoped data from existing + new API endpoints.

### What Changes
- **Frontend**: Complete rewrite of `base.html` → new layout with sidebar + main content
- **Frontend**: Single `index.html` template replaces 8 separate templates
- **Backend**: New context-aware API endpoints (scoped fixtures, scoped rankings, scoped chart data, scoped accuracy)
- **Backend**: New catch-all route replacing individual page routes
- **Assets**: EloKit logo, generic placeholder icons (club, league, cup), nation flags

### What Stays
- All existing API endpoints remain (backward compatible)
- Database schema unchanged
- Alpine.js + ApexCharts + Tailwind CSS stack
- Search functionality (enhanced with sidebar navigation)

## Tasks

### Task 1: Backend — Context-Aware API Endpoints
**Role:** `/fullstack` | **Effort:** ~6h | **Priority:** P0

The new unified layout needs scoped data. Extend existing endpoints and add new ones.

**New/Modified endpoints:**

1. **`GET /api/rankings`** — Add `league` filter param (existing has `country` and `date`)
   - League filter: return teams playing in that competition
   - Team context: return ±3 teams surrounding the given team in its domestic league

2. **`GET /api/rankings/context`** — New endpoint for team-context rankings
   - Params: `team_id` (required)
   - Returns: the team + 3 above + 3 below in its domestic league ranking

3. **`GET /api/fixtures/scoped`** — New endpoint for scoped fixtures
   - Params: `country`, `competition`, `team_id`, `status` (finished/scheduled/both), `limit`
   - Returns: up to N recent finished + N upcoming fixtures for the given scope
   - Reuses existing fixtures + matches tables

4. **`GET /api/chart/scoped`** — New endpoint for scoped chart data
   - Params: `country`, `competition`, `team_id`, `top_n` (default 5)
   - Returns: rating history for top N teams in scope (or single team + optional comparison teams)

5. **`GET /api/accuracy/scoped`** — New endpoint for context-specific accuracy
   - Params: `country`, `competition`, `team_id`
   - Returns: prediction accuracy stats scoped to context

6. **`GET /api/sidebar`** — Navigation tree for sidebar
   - Returns: nations with their competitions (leagues/cups), plus European competitions
   - Cached (changes rarely)

7. **`GET /api/rankings`** — Add `7d_change` field
   - Each ranking entry includes Elo change over last 7 calendar days

**Deliverables:**
- New/modified endpoints in `backend/main.py`
- New Pydantic models in `backend/models.py`
- Helper queries (possibly in `src/db/repository.py` or inline)

**Exit criteria:**
- [ ] `/api/rankings?league=Premier+League` returns filtered rankings with 7d change
- [ ] `/api/rankings/context?team_id=42` returns ±3 surrounding teams
- [ ] `/api/fixtures/scoped?country=England&limit=3` returns 3 recent + 3 upcoming English fixtures
- [ ] `/api/chart/scoped?competition=Premier+League&top_n=5` returns top 5 PL team histories
- [ ] `/api/accuracy/scoped?country=England` returns England-scoped prediction accuracy
- [ ] `/api/sidebar` returns complete navigation tree
- [ ] All existing endpoints still work unchanged

---

### Task 2: Frontend — Base Layout & Sidebar
**Role:** `/fullstack` | **Effort:** ~5h | **Priority:** P0

Rewrite `base.html` with the new EloKit layout: logo + banner header, collapsible sidebar with nation/competition navigation, hamburger on mobile.

**Deliverables:**
- New `base.html` with:
  - EloKit logo (top-left), "Find team" search (top-right), permanent banner below header
  - Collapsible sidebar: nations with flags → expandable to leagues/cups, European competitions section, About link
  - Hamburger menu on mobile (sidebar collapses)
  - Breadcrumb navigation component
  - Main content area for section blocks
- Generic placeholder icons in `backend/static/icons/`:
  - `club.svg` — generic team shield
  - `league.svg` — generic league icon
  - `cup.svg` — generic cup icon
- Nation flag emojis or a small flag icon set (e.g., flag-icons CSS library)
- Sidebar populated via `GET /api/sidebar` using Alpine.js

**Exit criteria:**
- [ ] EloKit logo displayed in header
- [ ] Sidebar shows nations expandable to competitions
- [ ] Sidebar shows European club competitions
- [ ] Sidebar collapses on mobile with hamburger toggle
- [ ] Breadcrumb renders correctly for each context level
- [ ] Search box in top-right corner works as before
- [ ] Banner message visible below header

---

### Task 3: Frontend — Unified Page Template
**Role:** `/fullstack` | **Effort:** ~8h | **Priority:** P0

Create the single `index.html` template with all four content sections, each fetching scoped data based on the current navigation context.

**Deliverables:**
- `backend/templates/index.html` — unified template with 4 sections:
  1. **Fixtures block** (collapsible): shows scoped fixtures with probability bars, team logos, competition logos, clickable teams
  2. **Accuracy widget**: prediction accuracy % with trend badge, "See all" link
  3. **Elo history chart**: ApexCharts line chart with top N teams (or single team + comparison), "See all" link
  4. **Rankings table**: scoped rankings with rank, team (clickable), league, points, 7d change (green/red), "See all" link
- Alpine.js component that:
  - Parses the current URL path to determine context (global/nation/league/team)
  - Fetches appropriate scoped data from API endpoints
  - Handles loading states and empty states
- Each section has a "See all" link that navigates to a dedicated detail view (can link to existing pages initially)

**Exit criteria:**
- [ ] Root `/` shows global fixtures, chart, accuracy, rankings
- [ ] `/england` shows England-scoped content
- [ ] `/england/premier-league` shows PL-scoped content
- [ ] `/england/premier-league/liverpool` shows Liverpool-scoped content
- [ ] Fixtures section is collapsible
- [ ] Teams are clickable in fixtures and rankings (navigate to team context)
- [ ] Chart shows correct teams for each context
- [ ] Rankings show 7d change with green/red coloring

---

### Task 4: Backend — Unified Route Handler
**Role:** `/fullstack` | **Effort:** ~3h | **Priority:** P0

Replace the current page routes with a single catch-all route that resolves the URL path and renders the unified template.

**Deliverables:**
- New route in `backend/main.py`:
  ```
  GET /{path:path}  →  renders index.html with context metadata
  ```
- Path resolver: maps URL slugs to DB entities:
  - `england` → country="England"
  - `premier-league` → competition name="Premier League"
  - `liverpool` → team name="Liverpool"
- Slug generation: `backend/slugs.py` — utility to create URL-safe slugs from nation/competition/team names
- Context object passed to template: `{ level: "team", country: "England", competition: "Premier League", team_id: 42, team_name: "Liverpool" }`
- Keep `/api/*` routes untouched (they must not be caught by the catch-all)
- Keep `/docs`, `/redoc`, `/openapi.json` routes untouched

**Exit criteria:**
- [ ] `/england/premier-league/liverpool` resolves to correct team context
- [ ] `/england` resolves to country context
- [ ] Invalid paths return 404
- [ ] `/api/*` endpoints unaffected
- [ ] Slugs are URL-safe and deterministic (e.g., "La Liga" → "la-liga")

---

### Task 5: Frontend — Fixture Cards Component
**Role:** `/fullstack` | **Effort:** ~4h | **Priority:** P1

Build the fixture card component matching the wireframe design — the most visually complex piece.

**Deliverables:**
- Fixture card with:
  - Competition logo (generic placeholder) on the left
  - Team names with club logos (generic placeholder)
  - Elo ratings for both teams
  - Score (finished matches) or date/time (upcoming)
  - Probability bar: colored segments (home green / draw yellow / away red)
  - Clickable team names → navigate to team context
- Finished vs. upcoming visual distinction (past matches slightly muted)
- Collapsible container with smooth animation

**Exit criteria:**
- [ ] Finished fixtures show score and probability bar
- [ ] Upcoming fixtures show date and prediction bar
- [ ] Generic competition and club icons displayed
- [ ] Clicking team name navigates to team page
- [ ] Collapse/expand animation works smoothly

---

### Task 6: Frontend — Rankings Table & Accuracy Widget
**Role:** `/fullstack` | **Effort:** ~3h | **Priority:** P1

Build the rankings table and accuracy widget matching the wireframe.

**Deliverables:**
- Rankings table: Rank | Team (clickable, with generic club icon) | League | Points | Last week
  - "Last week" shows 7d Elo change: green positive, red negative
  - Team context: shows ±3 surrounding teams with target team highlighted
  - League dropdown filter
- Accuracy widget:
  - Large accuracy percentage
  - Trend badge (e.g., "+1.5%" in green)
  - "See all" link to `/accuracy` page

**Exit criteria:**
- [ ] Rankings table shows correct data for each scope
- [ ] 7d change colored correctly
- [ ] Team context shows surrounding teams with highlight
- [ ] Accuracy widget shows context-specific accuracy
- [ ] "See all" links work

---

### Task 7: Static Assets & Branding
**Role:** `/fullstack` | **Effort:** ~2h | **Priority:** P1

Set up all static assets needed for the redesign.

**Deliverables:**
- `backend/static/logos/elokit-logo.png` — copy from `docs/wireframes/logos/`
- `backend/static/icons/club.svg` — generic shield icon
- `backend/static/icons/league.svg` — generic league icon
- `backend/static/icons/cup.svg` — generic cup icon
- Nation flags: use flag emoji or CSS flag-icons library
- Favicon updated to EloKit logo

**Exit criteria:**
- [ ] EloKit logo renders in header
- [ ] Generic icons display next to teams, leagues, and cups
- [ ] Nation flags display in sidebar
- [ ] Favicon updated

---

### Task 8: Retire Old Templates & Routes
**Role:** `/fullstack` | **Effort:** ~2h | **Priority:** P2

Clean up the old multi-page structure after the new layout is working.

**Deliverables:**
- Remove old page templates: `rankings.html`, `compare.html`, `predict.html`, `fixtures.html`, `prediction_history.html`, `accuracy.html`, `team.html`
- Remove old page routes from `main.py` (`/`, `/predict`, `/compare`, `/team/{id}`, `/fixtures`, `/prediction-history`, `/accuracy`)
- Add redirects from old paths to new equivalents (e.g., `/team/42` → `/england/premier-league/liverpool`)
- Update any hardcoded links

**Exit criteria:**
- [ ] No old templates remain (except `base.html` which is rewritten)
- [ ] Old URLs redirect to new equivalents
- [ ] No broken links

---

### Task 9: Responsive Design & Polish
**Role:** `/fullstack` | **Effort:** ~3h | **Priority:** P2

Ensure the layout works well across screen sizes and matches the wireframe aesthetics.

**Deliverables:**
- Mobile layout: sidebar as slide-out overlay, stacked sections
- Tablet layout: narrower sidebar, slightly compressed cards
- Desktop layout: full sidebar + main content as in wireframe
- Visual polish: spacing, typography, colors matching wireframe style
- Breadcrumb truncation on small screens

**Exit criteria:**
- [ ] Layout renders correctly on mobile (375px)
- [ ] Layout renders correctly on tablet (768px)
- [ ] Layout renders correctly on desktop (1280px+)
- [ ] Sidebar overlay works on mobile with hamburger toggle
- [ ] No horizontal scrolling on any breakpoint

---

### Task 10: Tests & Regression Check
**Role:** `/test-runner` | **Effort:** ~2h | **Priority:** P2

**Deliverables:**
- Run full test suite — no regressions
- Test new API endpoints (scoped fixtures, chart, accuracy, sidebar, rankings context)
- Verify old API endpoints unchanged
- Add tests for slug resolution and path routing

**Exit criteria:**
- [ ] All existing 363 tests passing
- [ ] New endpoint tests passing
- [ ] Slug resolution tests for edge cases (special characters, accents)

## Task Dependencies

```
Task 1 (Backend APIs) ──▶ Task 3 (Unified Template)
                      ──▶ Task 5 (Fixture Cards)
                      ──▶ Task 6 (Rankings & Accuracy)

Task 2 (Base Layout)  ──▶ Task 3 (Unified Template)

Task 4 (Route Handler) ──▶ Task 3 (Unified Template)

Task 7 (Assets)       ──▶ Task 2 (Base Layout)
                      ──▶ Task 5 (Fixture Cards)

Task 3 (Unified Template) ──▶ Task 8 (Retire Old)
                          ──▶ Task 9 (Responsive)

Task 8, Task 9 ──▶ Task 10 (Tests)
```

**Parallel tracks:**
- Track A: Tasks 1 + 4 (backend) can run in parallel
- Track B: Task 7 (assets) can run independently
- Track C: Tasks 2, 3, 5, 6 (frontend) are sequential but 5 and 6 can be parallel after 3

## Out of Scope

- **Real club/competition logos** — deferred to a future milestone (logo sourcing)
- **Historical prediction backfill** — was originally in Sprint 12 scope, deferred to Sprint 12.5 to keep this sprint focused on the redesign
- **Chart export (PNG/CSV)** — M4.5, Sprint 13
- **Predict page** — the standalone prediction widget is absorbed into the unified layout (users can predict from any context); if a dedicated predict page is needed, it's a follow-up
- **"See all" detail pages** — initial implementation links to existing pages or shows expanded inline views; dedicated detail pages can follow

## Risks

1. **Slug collisions** — "Liverpool" exists in both "Premier League" context and potentially as a standalone name. Mitigated by hierarchical URL structure (nation/league/team).
2. **Performance** — Loading 4 data sections per page load could be slow. Mitigate with parallel API calls in Alpine.js and lazy loading (chart only loads when scrolled into view).
3. **Scope creep** — The "See all" detail views could balloon. MVP: link to existing pages, iterate later.
4. **Accuracy widget** — Context-specific accuracy requires enough scored predictions in that scope. May show "insufficient data" for narrow contexts (single team).

## Definition of Done

- [ ] Single unified layout renders for all 4 context levels (global, nation, league, team)
- [ ] Sidebar navigation with nations, leagues, and European competitions
- [ ] Fixtures, accuracy, chart, and rankings all scope correctly to context
- [ ] EloKit branding (logo, name) throughout
- [ ] Mobile responsive with hamburger sidebar
- [ ] Existing API endpoints backward compatible
- [ ] All tests passing, no regressions
- [ ] Old templates removed, old URLs redirect
