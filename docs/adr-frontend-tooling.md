# ADR: Frontend Tooling Selection

**Status:** DECIDED
**Date:** 2026-03-13
**Deciders:** Product Team
**Context:** Sprint 6 — Frontend tooling decision for Sprint 7 implementation

---

## Context

The Football Elo Rating web application needs a frontend that displays:
- **Rankings tables** (sortable, filterable by league/country)
- **Team detail pages** with rating history
- **Interactive Elo trajectory charts** (zoomable, tooltips)
- **Match prediction widget** (team selectors, probability display)
- **Historical date explorer** (date picker → rankings at that date)

We need to choose frontend tooling that balances interactivity requirements with project constraints.

## Project Constraints

1. **Stack preference**: Tailwind CSS for styling (already adopted)
2. **No-framework default**: Prefer minimal JavaScript, avoid SPA complexity unless necessary
3. **Developer experience**: Minimize build tooling overhead
4. **Performance**: Fast time-to-interactive, small bundle size
5. **Backend**: FastAPI + Jinja2 templating already in use

## Options Evaluated

### 1. HTMX + Tailwind

**Approach:** Server-rendered HTML with HTMX for dynamic updates.

**Pros:**
- Minimal JavaScript (~14kb minified)
- Server-side rendering aligns with FastAPI/Jinja2
- Progressive enhancement
- No build step required
- Excellent for partial page updates (AJAX-like without writing JS)

**Cons:**
- Limited client-side interactivity (charts require separate library)
- Not ideal for complex client-side state (e.g., multi-step filters)
- Charting would need a standalone library anyway

**Fit:** Good for rankings tables, team detail pages, search. **Weak for interactive charts.**

### 2. Alpine.js + Tailwind

**Approach:** Lightweight reactive framework for sprinkles of interactivity.

**Pros:**
- Very lightweight (~15kb, no build step)
- Declarative syntax (similar to Vue)
- Works well with server-rendered HTML
- Good for interactive widgets (dropdowns, toggles, simple forms)
- Complements HTMX nicely

**Cons:**
- Not designed for complex state management
- Still needs a charting library for Elo trajectories
- Limited to DOM manipulation and reactivity

**Fit:** Good for team selectors, filters, date pickers. **Still weak for charts.**

### 3. Chart.js / Plotly.js (Standalone Charting)

**Charting libraries only** — must be combined with HTMX or Alpine for page interactivity.

#### Chart.js
- **Pros:** Lightweight (~200kb), simple API, good for line charts
- **Cons:** Less interactive than Plotly, fewer chart types
- **Fit:** Sufficient for Elo trajectory line charts

#### Plotly.js
- **Pros:** Highly interactive (zoom, pan, hover tooltips), rich chart types, publication-quality
- **Cons:** Larger bundle (~3.5MB full, ~1MB basic bundle), heavier performance
- **Fit:** Excellent for data exploration, but may be overkill

#### uPlot
- **Pros:** Extremely lightweight (~45kb), very fast rendering, designed for time-series
- **Cons:** Lower-level API, less feature-rich
- **Fit:** Great performance for Elo trajectories, minimal overhead

### 4. Full SPA (React / Vue / Svelte)

**Approach:** Build a client-side single-page application.

**Pros:**
- Maximum interactivity and rich UX
- Large ecosystem of components and libraries
- Well-suited for complex state management

**Cons:**
- Requires build tooling (Vite, webpack, etc.)
- Larger bundle sizes (React ~130kb, Vue ~90kb, Svelte ~50kb + dependencies)
- Deviates significantly from no-framework preference
- Server-side rendering becomes more complex (or is abandoned)
- Overkill for a mostly data-display application

**Fit:** Only justified if simpler options prove insufficient. **Not recommended.**

---

## Decision

**Primary tooling:** **HTMX + Alpine.js + Tailwind CSS**
**Charting library:** **Chart.js**

### Rationale

1. **HTMX** for server-rendered dynamic updates:
   - Rankings pagination and filtering
   - Team search with live results
   - Historical date queries

2. **Alpine.js** for client-side interactivity:
   - Team selector dropdowns in prediction widget
   - Date picker interactions
   - Toggle filters (league, country)
   - Show/hide UI elements

3. **Chart.js** for Elo trajectory visualization:
   - Lightweight (~200kb) vs Plotly (~1MB+)
   - Interactive enough (hover tooltips, responsive)
   - Simple API for line charts
   - Good browser compatibility

4. **Tailwind CSS** (already adopted):
   - Utility-first styling
   - Responsive design built-in
   - Consistent design system

### Architecture Pattern

```
┌─────────────────────────────────────┐
│  FastAPI Backend (Jinja2 templates) │
│  - Server-rendered HTML             │
│  - HTMX attributes for AJAX updates │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│  HTMX (14kb)                        │
│  - Partial page updates             │
│  - Server-driven state              │
└─────────────────────────────────────┘
              +
┌─────────────────────────────────────┐
│  Alpine.js (15kb)                   │
│  - Client-side reactivity           │
│  - Form interactions                │
└─────────────────────────────────────┘
              +
┌─────────────────────────────────────┐
│  Chart.js (200kb)                   │
│  - Elo trajectory line charts       │
│  - Hover tooltips                   │
└─────────────────────────────────────┘
              +
┌─────────────────────────────────────┐
│  Tailwind CSS                       │
│  - Utility classes                  │
│  - Responsive design                │
└─────────────────────────────────────┘
```

**Total JS payload:** ~229kb (minified, pre-gzip) — excellent for a data visualization app.

---

## Consequences

### Positive
- ✅ No build step required (all libraries CDN-compatible)
- ✅ Small bundle size → fast load times
- ✅ Server-side rendering keeps backend simple
- ✅ Progressive enhancement strategy
- ✅ Easy to adopt incrementally (HTMX first, Alpine where needed)
- ✅ Minimal learning curve for future contributors

### Negative
- ⚠️ Less "app-like" feel than a full SPA (but not a requirement)
- ⚠️ Multi-step client-side workflows require careful Alpine.js state management
- ⚠️ Chart.js less powerful than Plotly.js (acceptable trade-off)

### Neutral
- Charts are isolated to specific pages (team detail) — won't impact rankings page performance
- Can upgrade to Plotly.js later if Chart.js proves insufficient

---

## Implementation Notes

### CDN Links (for Sprint 7)
```html
<!-- HTMX -->
<script src="https://unpkg.com/htmx.org@2.0.4"></script>

<!-- Alpine.js -->
<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>

<!-- Chart.js -->
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>

<!-- Tailwind CSS -->
<script src="https://cdn.tailwindcss.com"></script>
```

Or install via npm/uv for production builds (recommended):
```bash
uv add htmx
uv add alpinejs
uv add chart.js
```

### Example: HTMX Pagination
```html
<div hx-get="/api/rankings?page=2" hx-target="#rankings-table" hx-swap="innerHTML">
  Load More
</div>
```

### Example: Alpine.js Team Selector
```html
<div x-data="{ homeTeam: '', awayTeam: '' }">
  <select x-model="homeTeam">...</select>
  <select x-model="awayTeam">...</select>
  <button @click="predict(homeTeam, awayTeam)">Predict</button>
</div>
```

### Example: Chart.js Elo Trajectory
```javascript
const ctx = document.getElementById('eloChart').getContext('2d');
new Chart(ctx, {
  type: 'line',
  data: {
    labels: dates,
    datasets: [{
      label: 'Elo Rating',
      data: ratings,
      borderColor: 'rgb(59, 130, 246)',
      tension: 0.1
    }]
  }
});
```

---

## Alternatives Considered But Rejected

- **Vanilla JS only:** Too much boilerplate for AJAX and reactivity
- **jQuery:** Outdated, larger than HTMX+Alpine combined
- **Full SPA frameworks:** Overkill for this use case, violates no-framework preference
- **Plotly.js:** Too heavy (3x the size of Chart.js) for marginal gain

---

## References

- [HTMX Documentation](https://htmx.org/)
- [Alpine.js Documentation](https://alpinejs.dev/)
- [Chart.js Documentation](https://www.chartjs.org/)
- [Tailwind CSS Documentation](https://tailwindcss.com/)
