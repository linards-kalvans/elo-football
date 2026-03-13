# Sprint 7 — Frontend, Predictions & Deployment

**Depends on:** Sprint 6 completed (backend API documented and running)
**Status:** IN PROGRESS (Started 2026-03-14)
**Goal:** Build the complete frontend using Sprint 6's API contract, add prediction and historical features, and deploy to production.

**Deployment target:** Hetzner VPS (Docker container)
**Frontend structure:** backend/templates/ + backend/static/ (co-located with FastAPI)
**Chart.js scope:** Basic line charts (zoom/pan/multi-team overlay deferred to M4.5)

---

## Items

### 1. Frontend: Rankings & Navigation

**Priority:** P1 | **Impact:** High

Core pages using the frontend tooling chosen in Sprint 6 ADR.

**Pages:**
- **Home / Rankings** — Sortable table of current Elo rankings, filterable by league. Fetches from `GET /api/rankings`.
- **League selector** — Switch between EPL, La Liga, Bundesliga, Serie A, Ligue 1, or Global view
- **Navigation** — Header with league tabs, search bar, links to prediction tool
- **Search** — Team name search via `GET /api/search?q={query}`

**Deliverables:**
- Responsive layout with Tailwind
- Rankings table with sorting and league filtering
- Team name links to team detail page
- Loading states and error handling

### 2. Frontend: Team Detail Page

**Priority:** P1 | **Impact:** High

Per-team page showing rating history and context.

**Components:**
- Interactive Elo trajectory chart (using charting lib from Sprint 6 ADR)
- Current rating, rank, league
- Recent match results with Elo deltas
- Compare with other teams (add/remove teams on the chart)

**Deliverables:**
- Team detail page at `/team/{team_id}`
- Interactive chart with zoom, hover tooltips, multi-team overlay
- Recent matches table

### 3. Match Prediction Widget

**Priority:** P1 | **Impact:** High

Interactive tool for users to predict match outcomes.

**Features:**
- Select home team and away team (searchable dropdowns, filtered by league or global)
- Display: home win %, draw %, away win % — as a visual bar or gauge
- Show current Elo ratings for both teams and the rating gap
- Optional: venue toggle (neutral ground scenario — removes home advantage)

**Deliverables:**
- Prediction page at `/predict`
- Calls `GET /api/predict?home={id}&away={id}`
- Clear, intuitive visualization of probabilities
- Mobile-friendly layout

### 4. Historical Date Explorer

**Priority:** P2 | **Impact:** Medium

Allow users to view ratings at any historical point in time.

**Features:**
- Date picker input → fetch rankings at that date via `GET /api/rankings?date=YYYY-MM-DD`
- Rankings table updates dynamically
- Timeline slider for quick exploration across seasons
- Visual indicator of which season the selected date falls in

**Deliverables:**
- Date picker component integrated into rankings page
- Smooth transitions when date changes
- URL updates with date parameter (shareable links)

### 5. Polish & Performance

**Priority:** P2 | **Impact:** Medium

Production readiness for the frontend.

**Items:**
- SEO: meta tags, page titles, Open Graph tags for social sharing
- Performance: lazy-load charts, paginate large tables, cache API responses
- Accessibility: keyboard navigation, ARIA labels, color contrast
- Error pages: 404, 500, API timeout handling
- Favicon, branding, footer with data source attribution

### 6. Deployment

**Priority:** P1 | **Impact:** High

Ship to production.

**Deliverables:**
- Dockerfile (multi-stage: build frontend assets → serve with FastAPI)
- `docker-compose.yml` for local development (app + database if needed)
- Hosting decision and setup (candidates: Fly.io, Railway, VPS, or similar)
- CI/CD: GitHub Actions pipeline for lint → test → build → deploy
- Environment variable management for production secrets
- Basic monitoring / logging setup

---

## Acceptance Criteria

- [ ] Rankings page renders current ratings for all leagues
- [ ] Team detail page shows interactive Elo trajectory chart
- [ ] Search works for team names
- [ ] Match prediction widget works for any team pair across all leagues
- [ ] Historical date picker shows accurate ratings at any past date
- [ ] Responsive on mobile and desktop
- [ ] Application deployed and accessible via public URL
- [ ] Docker build works locally and in CI
- [ ] CI/CD pipeline runs: lint → test → build → deploy
- [ ] Page load time < 2s on 3G connection for rankings page

## Out of Scope

- User accounts / personalization
- Live match tracking / real-time updates
- Betting odds integration
- Mobile native app
