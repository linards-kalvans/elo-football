# Sprint 6 — Backend API & Documentation

**Depends on:** Sprint 5 completed (database, pipeline, prediction API)
**Status:** COMPLETED (2026-03-13)
**Goal:** Ship a fully documented FastAPI backend with comprehensive API contracts, enabling frontend development to proceed independently.

---

## Items

### 0. Frontend Tooling ADR

**Priority:** P1 | **Impact:** High | **Blocks:** Sprint 7 frontend work

Decide on frontend tooling before Sprint 7 begins. This is research-only — no frontend code in this sprint.

**Options to evaluate:**

| Option | Pros | Cons | Fit |
|--------|------|------|-----|
| **HTMX + Tailwind** | Server-rendered, minimal JS, works with FastAPI/Jinja2, progressive enhancement | Limited client-side interactivity, charting needs separate lib | Good for mostly-static pages with some dynamic elements |
| **Alpine.js + Tailwind** | Lightweight (~15kb), declarative, no build step, pairs well with HTMX | Not suited for complex state management | Good middle ground — interactive widgets without SPA overhead |
| **Plotly.js / Chart.js** (standalone charting) | Purpose-built for data viz, interactive out of the box | Only covers charts, still need something for page interactivity | Combine with HTMX or Alpine for a full solution |
| **Full SPA (React/Vue/Svelte)** | Maximum interactivity, rich ecosystem | Build tooling overhead, heavier, deviates from stack preferences | Only if simpler options prove insufficient |

**Evaluation criteria:**
- Interactivity needs (charting, filtering, dynamic tables)
- Developer experience (build step? bundler? type safety?)
- Performance budget (time-to-interactive, bundle size)
- Alignment with existing stack preferences (Tailwind, no-framework default)
- Charting library selection (Plotly.js, Chart.js, uPlot, or similar)

**Deliverables:**
- ADR document: `docs/adr-frontend-tooling.md`
- Decision on charting library

### 1. FastAPI Backend

**Priority:** P1 | **Impact:** High

Build the HTTP API layer on top of the Sprint 5 Python API and database.

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/rankings` | Current rankings (all leagues or filtered by league) |
| `GET` | `/api/rankings?date=YYYY-MM-DD` | Historical rankings at a given date |
| `GET` | `/api/teams/{team_id}` | Team detail: current rating, rating history, recent matches |
| `GET` | `/api/teams/{team_id}/history` | Full Elo trajectory for charting |
| `GET` | `/api/predict?home={id}&away={id}` | Match prediction (win/draw/loss probabilities) |
| `GET` | `/api/leagues` | List of available leagues |
| `GET` | `/api/search?q={query}` | Team name search |
| `GET` | `/api/health` | Health check |

**Deliverables:**
- FastAPI app in `backend/` with async routes
- Pydantic response models for all endpoints with field descriptions
- CORS configuration for frontend
- Tests for all endpoints
- Error handling middleware with consistent error response shape

### 2. API Documentation

**Priority:** P1 | **Impact:** High | **Depends on:** item 1

Comprehensive API documentation that enables frontend development without backend access.

**Deliverables:**

#### 2a. API Contract Document (`docs/api-contract.md`)
- Every endpoint fully specified: method, path, query params, path params
- Request/response examples (JSON) for every endpoint
- Pagination conventions (offset/limit or cursor-based)
- Filtering and sorting conventions
- Error response catalog with HTTP status codes and error body shape
- Rate limiting policy (if any)
- CORS policy

#### 2b. Pydantic Response Models (in code)
- All response models with `Field(description=..., example=...)` annotations
- Nested models documented (e.g., `TeamSummary` inside `RankingsResponse`)
- Enum values documented (league codes, sort fields)

#### 2c. Auto-Generated OpenAPI
- FastAPI `/docs` (Swagger UI) and `/redoc` endpoints enabled
- OpenAPI spec exportable as JSON (`/openapi.json`) for frontend tooling
- Endpoint descriptions and tags for logical grouping

#### 2d. Example Responses (`docs/api-examples/`)
- One JSON file per endpoint with realistic example data
- Covers success cases, empty results, and error cases
- Frontend developers can use these as mock data during development

### 3. Database Integration

**Priority:** P1 | **Impact:** High | **Depends on:** item 1

Wire the FastAPI backend to the Sprint 5 database layer.

**Deliverables:**
- Database connection management (async session lifecycle)
- Query layer: repository pattern or similar abstraction between API routes and raw SQL
- Seed script verification: confirm all historical data queryable through API
- Performance: add database indexes for API query patterns if not already present
- Integration tests: API → database round-trip tests

---

## Acceptance Criteria

- [x] Frontend tooling ADR written and decision made
- [x] FastAPI backend running with all listed endpoints
- [x] All endpoints return correctly shaped Pydantic responses
- [x] API contract document covers every endpoint with request/response examples
- [x] Example JSON responses exist for every endpoint (success + error cases)
- [x] OpenAPI spec is complete and exportable at `/openapi.json`
- [x] API tests pass (unit + integration) — 153 total tests passing
- [x] Error responses follow a consistent shape across all endpoints
- [x] A frontend developer can build against the API using only `docs/api-contract.md` + example responses

## Out of Scope

- Frontend code (Sprint 7)
- Deployment / Docker / CI/CD (Sprint 7)
- User accounts / authentication
- Real-time / live match updates
