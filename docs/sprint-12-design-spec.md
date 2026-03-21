# Sprint 12 — EloKit Redesign Design Spec

## App Identity
- **Name**: EloKit
- **Logo**: `docs/wireframes/logos/elokit-logo.png`
- **Wireframe**: `docs/wireframes/EloKit Wireframe-Page 1.png`

## Core Concept: Unified Single-Page Layout

One layout for all contexts — landing page, nation, league/cup, and team. The **content is scoped** based on the selected context; the layout stays the same.

### Navigation Contexts
- **Root `/`** — Global: all teams, all competitions
- **Nation** (e.g., `/england`) — All teams from that nation across all leagues/cups
- **League/Cup** (e.g., `/england/premier-league`) — All current teams in that competition
- **Team** (e.g., `/england/premier-league/liverpool`) — Single team view

## Page Layout (top to bottom)

### 1. Header
- EloKit logo (top-left)
- **"Find team" search box** (top-right corner)
- Permanent banner message below logo (e.g., "Buy me a coffee" link)

### 2. Breadcrumb Navigation
- Contextual path: `EloKit > England > Premier League > Liverpool`
- Each segment is clickable to navigate up the hierarchy

### 3. Fixtures (collapsible)
- Up to **3 finished** (most recent) + up to **3 upcoming** matches
- Scoped to selected context:
  - Root: all competitions
  - Nation: all that nation's fixtures across leagues/cups
  - League: that league's fixtures
  - Team: that team's fixtures
- Each fixture shows:
  - Competition logo (next to fixture)
  - Club logos (next to team names)
  - Elo ratings for both teams
  - Score (finished) or date/time (upcoming)
  - Probability bar (win/draw/loss segments)
- Teams are **clickable** (navigate to team page)
- **"See all"** link to detailed fixtures view

### 4. Accuracy Widget
- Prediction accuracy percentage with trend indicator (e.g., +1.5%)
- **Context-specific**: shows accuracy for the selected scope (global, nation, league, team)
- Links to detailed accuracy view via "See all"

### 5. Elo History Chart (interactive)
- Scoped to context:
  - Root / Nation / League: **top N teams** as line chart
  - Team: that team's Elo line, with **option to add other teams** for comparison
- **"See all"** link to full chart view

### 6. Elo Rankings Table
- Columns: Rank, Team, League, Points, Last week change
- **"Last week"** = Elo change over last **7 calendar days**
- Scoped to context:
  - Root: global rankings, all teams
  - Nation: all teams from that nation
  - League: teams in that league
  - Team: surrounding teams in its domestic league — **the team +3 above and +3 below**
- Teams are **clickable**
- League dropdown/filter available
- **"See all"** link to full rankings view

## Side Menu
- **Nation leagues**: list of nations (with flags), each expandable to show competitions (leagues/cups)
  - e.g., England → Premier League, Championship
- **European club competitions**: Champions League, Europa League, Conference League (with competition logos)
- **About** link at bottom
- Collapses on mobile (**hamburger menu**)

### Logo/Icon Strategy
- **MVP**: use generic placeholder logos:
  - Generic club logo for teams
  - Generic league logo (indicating tier) for leagues
  - Generic cup logo for cup competitions
  - Nation flags for nations (these are readily available)
- **Future milestone**: source real club/competition logos (separate task)

## Visual References
- Each entry in fixtures/rankings has logos next to it
- Probability bars use colored segments (green/yellow/red style)
- Chart uses distinct line colors per team
- Rankings show positive changes in green, negative in red
