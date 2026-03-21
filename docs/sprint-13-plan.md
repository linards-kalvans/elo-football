# Sprint 13 Plan — Nation Flags & Competition Logos

> Status: COMPLETED (2026-03-17)
> Depends on: Sprint 12.1 (completed)
> Milestones: M12 (Flags & Logos — Phase 1)

## Goals

Replace placeholder flag emojis and generic SVG icons with real country flag images and competition logos. This is Phase 1 of M12 — club crests are deferred to Phase 2.

**Current state:** The sidebar uses hardcoded flag emojis via a JS function (`flagEmoji()`), and all competitions use either `league.svg` or `cup.svg` generic icons. These appear in the sidebar, fixtures, rankings, chart search, and breadcrumbs.

## Scope

### In Scope
- SVG country flags for all 5 nations + Europe (sidebar, breadcrumbs)
- Official-style competition logos for 5 domestic leagues + 3 European cups (sidebar, fixtures headers)
- Breadcrumb flag/logo integration
- Graceful fallback for missing assets

### Out of Scope
- Club crests/logos (M12 Phase 2)
- Chart export (M4.5, Sprint 14)
- Historical prediction backfill (M9)

---

## Tasks

### Task 1: Source & Bundle Country Flag SVGs
**Role:** `/fullstack` | **Effort:** ~1h | **Priority:** P0

Source SVG flag files for the 5 nations + a Europe/EU flag. Bundle them as static assets.

**Deliverables:**
- `backend/static/flags/` directory with SVG files:
  - `england.svg`, `spain.svg`, `germany.svg`, `italy.svg`, `france.svg`, `europe.svg`
- Source: [flag-icons](https://github.com/lipis/flag-icons) (MIT license, 4x3 SVGs) or [flagcdn.com](https://flagcdn.com) downloaded locally
- England needs the St George's Cross (not Union Jack) — use `gb-eng.svg` from flag-icons

**Exit criteria:**
- [x] 6 SVG flag files in `backend/static/flags/`
- [x] England flag is St George's Cross, not Union Jack
- [x] All flags render at 20×15px and 24×18px without distortion

---

### Task 2: Create Competition Logo Assets
**Role:** `/fullstack` | **Effort:** ~2h | **Priority:** P0

Create or source simple, recognizable logo images for each competition. These don't need to be official logos — stylized representations are fine for an analytics tool.

**Deliverables:**
- `backend/static/logos/competitions/` directory with SVG/PNG files:
  - Domestic: `premier-league.svg`, `la-liga.svg`, `bundesliga.svg`, `serie-a.svg`, `ligue-1.svg`
  - European: `champions-league.svg`, `europa-league.svg`, `conference-league.svg`
- Sizing: consistent height (24px display), square or landscape aspect ratio
- If sourcing official logos is problematic (licensing), create minimal text-based or icon-based alternatives

**Exit criteria:**
- [x] 8 competition logo files in `backend/static/logos/competitions/`
- [x] Consistent visual weight and sizing
- [x] Files load without CORS or path issues

---

### Task 3: Backend — Add Flag & Logo URLs to API Responses
**Role:** `/fullstack` | **Effort:** ~2h | **Priority:** P0

Extend API responses to include URLs for flag and competition logo assets, so the frontend doesn't need hardcoded path logic.

**Deliverables:**

1. **`/api/sidebar` response** — add `flag_url` to each nation, `logo_url` to each competition:
   ```json
   {
     "nations": [{
       "country": "England",
       "flag_url": "/static/flags/england.svg",
       "competitions": [{
         "id": 1,
         "name": "Premier League",
         "type": "league",
         "logo_url": "/static/logos/competitions/premier-league.svg"
       }]
     }],
     "european": [{
       "id": 6,
       "name": "Champions League",
       "type": "cup",
       "logo_url": "/static/logos/competitions/champions-league.svg"
     }]
   }
   ```

2. **`/api/fixtures/scoped` response** — add `competition_logo_url` to each fixture group or match

3. **Slug-to-asset mapping** — utility function in backend that maps country/competition names to their asset paths (reuse existing slug logic from Sprint 12)

4. **Pydantic model updates** — add `Optional[str]` fields: `flag_url`, `logo_url`, `competition_logo_url`

**Files modified:**
- `backend/main.py` — sidebar endpoint, fixtures endpoint
- `backend/models.py` — new optional URL fields

**Exit criteria:**
- [x] `/api/sidebar` returns `flag_url` for each nation
- [x] `/api/sidebar` returns `logo_url` for each competition
- [x] `/api/fixtures/scoped` returns `competition_logo_url` for fixtures
- [x] Missing assets return `null` (not a broken URL)

---

### Task 4: Frontend — Replace Flag Emojis with Flag Images
**Role:** `/fullstack` | **Effort:** ~2h | **Priority:** P1

Replace the `flagEmoji()` JS function with `<img>` tags using the flag SVGs.

**Deliverables:**
- **Sidebar** (`base.html`): Replace `<span x-text="flagEmoji(nation.country)">` with `<img :src="nation.flag_url" class="w-5 h-4 inline-block rounded-sm">`
- **Breadcrumbs** (`base.html`): Add flag image next to nation name in breadcrumb trail
- **Remove** the `flagEmoji()` function from `base.html` (lines ~341-350)
- **Fallback**: If `flag_url` is null, show a generic globe icon or hide the image

**Files modified:**
- `backend/templates/base.html`

**Exit criteria:**
- [x] Sidebar shows real flag images instead of emojis
- [x] Breadcrumbs show flag next to nation name
- [x] `flagEmoji()` function removed
- [x] Graceful fallback for missing flags (no broken images)

---

### Task 5: Frontend — Replace Generic Icons with Competition Logos
**Role:** `/fullstack` | **Effort:** ~3h | **Priority:** P1

Replace `league.svg`/`cup.svg` generic icons with competition-specific logos throughout the UI.

**Deliverables:**
- **Sidebar** (`base.html`): Replace generic icons with `<img :src="comp.logo_url">` for each competition
- **Fixtures** (`index.html`): Replace `competitionIcon()` function output with competition logo from API data
  - Finished fixtures (lines ~65-66): use `competition_logo_url`
  - Upcoming fixtures (lines ~121-122): use `competition_logo_url`
- **Remove** the `competitionIcon()` function from `index.html` (lines ~812-818)
- **Fallback**: If `logo_url` is null, fall back to existing generic `league.svg` or `cup.svg` based on type

**Files modified:**
- `backend/templates/base.html` — sidebar competition items
- `backend/templates/index.html` — fixtures section, `competitionIcon()` removal

**Exit criteria:**
- [x] Sidebar shows competition-specific logos
- [x] Fixtures show competition logos instead of generic icons
- [x] `competitionIcon()` retained as fallback for entries without `competition_logo_url`
- [x] Fallback to generic icon if logo_url is missing

---

### Task 6: Tests & Regression Check
**Role:** `/test-runner` | **Effort:** ~1h | **Priority:** P2

**Deliverables:**
- Run full test suite — no regressions from 360 passing
- Add tests for new `flag_url` and `logo_url` fields in sidebar API response
- Verify fixtures API includes `competition_logo_url`
- Verify no broken image paths in API responses

**Exit criteria:**
- [x] All 364 tests passing (360 existing + 4 new)
- [x] New tests for flag/logo URL fields
- [x] No regressions in sidebar or fixtures endpoints

---

## Task Dependencies

```
Task 1 (Flag SVGs)  ──▶ Task 3 (Backend API) ──▶ Task 4 (Frontend Flags)
Task 2 (Comp Logos) ──▶ Task 3 (Backend API) ──▶ Task 5 (Frontend Logos)

Task 4, Task 5 ──▶ Task 6 (Tests)
```

**Parallel tracks:**
- Tasks 1 + 2 (asset sourcing) can run in parallel
- Tasks 4 + 5 (frontend integration) can run in parallel after Task 3

## Estimated Effort

| Task | Effort |
|------|--------|
| 1. Flag SVGs | ~1h |
| 2. Competition logos | ~2h |
| 3. Backend API changes | ~2h |
| 4. Frontend flags | ~2h |
| 5. Frontend competition logos | ~3h |
| 6. Tests | ~1h |
| **Total** | **~11h** |

## Risks

1. **Flag licensing**: flag-icons is MIT licensed; flags are public domain. Low risk.
2. **Competition logo licensing**: Official league logos may have trademark restrictions. Mitigation: use generic styled alternatives or text-only badges if needed.
3. **England vs UK flag**: Must use St George's Cross (England), not Union Jack (UK). The flag-icons library has `gb-eng.svg` for this.
4. **Asset loading performance**: 8 competition logos + 6 flags = 14 small SVGs. Negligible impact — SVGs are typically <5KB each.

## Definition of Done

- [x] Country flags render in sidebar and breadcrumbs (real SVG images, not emojis)
- [x] Competition logos render in sidebar and fixtures (specific to each competition)
- [x] API responses include asset URLs (`flag_url`, `logo_url`, `competition_logo_url`)
- [x] Graceful fallback for any missing assets
- [x] `flagEmoji()` removed; `competitionIcon()` retained as fallback
- [x] All 364 tests passing, no regressions
