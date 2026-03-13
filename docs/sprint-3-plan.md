# Sprint 3 — MoV Fix, Multi-League Domestic Expansion & Querying

**Status: COMPLETE** (2026-03-12)
**Depends on:** Sprint 2 completed
**Goal:** Fix MoV normalization, expand to top-5 European domestic leagues, add historical date queries. Cross-league calibration deferred to Sprint 4 pending European cup data sourcing.

---

## Scope Change Notice

**Items 2 (Competition Tier Weighting) and 3 (Cross-League Calibration) moved to Sprint 4.**

Reason: Both depend on European competition data (Champions League, Europa League) which is **not available** from Football-Data.co.uk. That source only provides domestic league CSVs. A new data source must be identified and ingested before these features can be implemented. See Sprint 4 plan for details.

Sprint 3 focuses on what we *can* deliver with domestic league data alone: parallel per-league Elo ratings with independent rating pools.

---

## Items

### 0. Normalize MoV Multiplier (1-goal baseline fix)

**Priority:** P1 | **Impact:** Medium | **Blocks:** Re-sweep (item 0b)

Sprint 2 introduced MoV but `ln(goal_diff + 1)` yields 0.693 for 1-goal wins, making them weighted *less* than draws (base K). Fix by normalizing so 1-goal difference = multiplier of 1.0:

```python
# In mov_multiplier():
ln_component = math.log(abs(goal_diff) + 1) / math.log(2)
```

Resulting effective K curve (base K=30, equal teams):

| Goal diff | Multiplier | K_eff |
|-----------|-----------|-------|
| 0 (draw)  | 1.0 (base)| 30    |
| 1         | 1.00      | 30    |
| 2         | 1.58      | 47    |
| 3         | 2.00      | 60    |
| 4         | 2.32      | 70    |

**Files:** `src/elo_engine.py` (1 line), update tests in `tests/test_elo_engine.py`.

### 0b. Re-sweep K-factor with normalized MoV

**Priority:** P1 | **Impact:** Medium | **Depends on:** item 0

The optimal K likely shifts now that 1-goal wins use full K. Run `param_sweep.py` (updated to use `EloEngine`) with MoV enabled across K=[20,30,40,50], spread=[400,500,600]. Update defaults in `src/config.py` and `.env.example`.

**Files:** `notebooks/param_sweep.py`, `src/config.py`, `.env.example`.

### 1. Multi-League Data Ingestion (domestic only)

**Priority:** P2 | **Impact:** High

Extend `data_ingest.py` and fetch scripts to support top-5 European domestic leagues:

| League | Football-Data.co.uk code | Division file |
|--------|-------------------------|---------------|
| EPL | E0 | `data/epl/<season>/E0.csv` (done) |
| La Liga | SP1 | `data/laliga/<season>/SP1.csv` |
| Bundesliga | D1 | `data/bundesliga/<season>/D1.csv` |
| Serie A | I1 | `data/seriea/<season>/I1.csv` |
| Ligue 1 | F1 | `data/ligue1/<season>/F1.csv` |

Deliverables:
- Generic `fetch_league_csvs.sh` parameterized by league code
- Per-league club name normalization maps
- Unified data schema (Date, HomeTeam, AwayTeam, FTHG, FTAG, FTR, Season, League)
- Validation: row counts, date parsing, team name consistency per league

**Note:** Each league gets an **independent Elo rating pool** — ratings are not comparable across leagues until cross-league calibration is implemented in Sprint 4.

### 2. Run per-league Elo ratings

**Priority:** P2 | **Impact:** Medium | **Depends on:** items 0, 0b, 1

Run `EloEngine` independently for each league. Produce per-league:
- Rankings table
- Elo trajectory plots
- Predictive accuracy metrics (log-loss, Brier, accuracy)

Compare model quality across leagues — if EPL-tuned parameters (K=30, spread=500) don't work well for Bundesliga or Ligue 1, flag for per-league tuning.

**Files:** `notebooks/run_analysis.py` (generalize), `notebooks/outputs/` (per-league subdirs).

### 3. Historical Date Query Interface

**Priority:** P3 | **Impact:** Medium

Enable querying ratings at any historical date:
- `engine.get_ratings_at(date="2022-01-15")` returns all team ratings as of that date
- Leverages the `history` dict already tracked in the engine
- Expose as a simple CLI or Python API
- Binary search over sorted history for efficient lookup

**Files:** `src/elo_engine.py` (add method), `tests/test_elo_engine.py` (add tests).

---

## Deferred to Sprint 4

European competition data sourcing, competition name/format normalization, tier weighting, and cross-league calibration are all covered in detail in [Sprint 4 plan](sprint-4-plan.md).
