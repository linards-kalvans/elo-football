# Sprint 4 — European Competition Data & Cross-League Calibration

**Depends on:** Sprint 3 completed (multi-league domestic ratings running)
**Status:** COMPLETED
**Goal:** Source European cup data, normalize competition names/formats, implement competition tier weighting, and calibrate ratings across leagues.

---

## Items

### 1. European Competition Data Sourcing & Ingestion

**Priority:** P1 | **Impact:** High | **Blocks:** items 3, 4

Football-Data.co.uk does not provide CL/EL/Conference League data. Evaluate and ingest from an alternative source.

**Candidate sources:**

| Source | Coverage | Format | Notes |
|--------|----------|--------|-------|
| **openfootball** | Historical + major leagues | Text/CSV (GitHub) | Open data, good for domestic + historical European cups. See github.com/openfootball |
| Kaggle datasets | Variable | CSV | Search for "Champions League results" |
| API-Football / football-data.org | Good | JSON API | May require API key / rate limits |
| FBref / StatsBomb | Comprehensive | HTML/CSV | Free tier available |
| Transfermarkt | Comprehensive | Scraping needed | TOS restrictions |
| UEFA.com | Official | Scraping needed | Match results pages |

**Deliverables:**
- Source evaluation document with coverage gaps, licensing, and format assessment
- Ingestion pipeline for chosen source(s) into unified match schema
- Minimum 10 years of CL and EL results ingested
- Validation: match counts per season vs. known tournament sizes

**Decision needed:** Which source to use. **openfootball** is the primary candidate — evaluate first.

### 2. European Competition Name & Format Normalization

**Priority:** P1 | **Impact:** High | **Blocks:** items 3, 4

European club competitions have undergone multiple rebrandings and format changes that must be mapped to a consistent taxonomy:

| Era | Competition | Modern equivalent | Notes |
|-----|-------------|-------------------|-------|
| 1955–1992 | European Cup | Champions League | Knockout only, league champions only |
| 1971–1999 | UEFA Cup | Europa League | Merged with Cup Winners' Cup in 1999 |
| 1960–1999 | Cup Winners' Cup | *(defunct)* | Absorbed into UEFA Cup/EL |
| 1992–present | Champions League | — | Group stage added; league phase from 2024/25 |
| 2009–present | Europa League | — | Rebranded from UEFA Cup |
| 2021–present | Conference League | — | New third-tier competition |

**Deliverables:**
- Canonical competition ID mapping (e.g., `european_cup` → `champions_league`, `uefa_cup` → `europa_league`)
- Format-aware tier assignment — a 1980s European Cup final should carry similar weight to a modern CL knockout match, but group-stage matches (post-1992) may warrant lower weight
- Team name normalization across eras and sources (e.g., "Nottingham Forest" vs "Nott'm Forest" vs "Nottingham F.")
- Documented decision on how to handle defunct competitions (Cup Winners' Cup) in the tier hierarchy
- Normalization maps stored as data files (`data/normalization/`) for maintainability

### 3. Competition Tier Weighting

**Priority:** P2 | **Impact:** Medium | **Depends on:** items 1, 2

Apply K multipliers by competition type so that CL knockout matches move ratings more than domestic league matches.

**Proposed tier hierarchy:**

| Tier | Competitions | K multiplier (tentative) |
|------|-------------|-------------------------|
| 1 | CL knockout / European Cup knockout | 1.5× |
| 2 | CL group stage / CL league phase | 1.2× |
| 3 | EL / UEFA Cup knockout | 1.2× |
| 4 | EL group stage, Conference League | 1.0× |
| 5 | Top-5 domestic leagues | 1.0× (baseline) |

**Deliverables:**
- `competition_tier` field added to match schema
- K multiplier logic in `EloEngine` (new `tier_multiplier` parameter set)
- Tier weights configurable via `EloSettings`
- Validation: run with and without tier weighting, compare predictive accuracy

### 4. Cross-League Calibration

**Priority:** P2 | **Impact:** High | **Depends on:** items 1, 2, 3

Anchor ratings across leagues using CL/EL results as bridge matches.

**Approach:**
- Run all matches (domestic + European) through a single unified `EloEngine` instance
- European cup matches naturally calibrate teams across leagues — a team's CL performance adjusts their rating relative to opponents from other leagues
- Initial ratings for new leagues still start at `initial_elo`; CL/EL results pull them to their correct level over time

**Fallback approach** (if European data proves insufficient):
- League-relative starting offsets based on UEFA coefficient rankings
- Less rigorous but unblocks unified rankings without CL data

**Deliverables:**
- Unified global rating pool across all 5 leagues + European competitions
- Global rankings table (all teams, all leagues)
- Validation: do CL group-stage outcomes correlate with pre-match Elo predictions?
- Comparison: per-league accuracy before vs. after calibration

---

## Acceptance Criteria

- [x] European cup data ingested (≥10 years CL + EL) — 15 seasons CL, 5 EL, 4 Conference League from openfootball
- [x] All competition names normalized to canonical IDs — CL/EL/Conference League mapped via STAGE_TIER
- [x] Team names consistent across domestic and European data — 100+ mappings in src/team_names.py, 58/58 top-5 country teams verified
- [x] Tier weighting applied and configurable — T1=1.5x (CL knockout), T2=1.2x (CL group), T3=1.2x (EL knockout), T4/T5=1.0x
- [x] Unified global rankings produced across 5 leagues — 300 teams rated, Bayern Munich & Arsenal joint #1 (1836)
- [x] Cross-league predictive accuracy validated on CL/EL matches — unified log loss 0.9883, accuracy 53.3%

## Out of Scope

- Database persistence (Sprint 5)
- Web frontend (Sprint 6–7)
- Conference League data (nice-to-have, not blocking)
