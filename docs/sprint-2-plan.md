# Sprint 2 — Model Refinement & Engine Extraction

**Depends on:** Sprint 1 completed
**Status:** COMPLETED (2026-03-12)
**Goal:** Improve rating differentiation with margin-of-victory, validate K-factor choice, and extract the Elo engine into a reusable module.

---

## Items

### 1. Margin-of-Victory Adjustment ✅

**Priority:** P2 | **Impact:** Medium

A 4-0 win should move ratings more than 1-0. Scale K by goal difference using the FiveThirtyEight formula:

```
K_adj = K * ln(goal_diff + 1) * (autocorr_coeff / (elo_diff * autocorr_scale + autocorr_coeff))
```

The autocorrelation correction prevents strong teams from being over-rewarded when beating weak opponents by large margins. FiveThirtyEight defaults: `autocorr_coeff=2.2`, `autocorr_scale=0.001`.

Add these to the `EloSettings` model from Sprint 1:
- `mov_autocorr_coeff: float = 2.2`
- `mov_autocorr_scale: float = 0.001`

**Delivered:** Implemented in `src/elo_engine.py` as `EloEngine.mov_multiplier()`. MoV only applies when `goal_diff > 0`; draws use base K. Parameters added to `EloSettings` and `.env.example`.

### 2. K-Factor Tuning via Backtesting ✅

**Priority:** P2 | **Impact:** Medium

Sweep `K` across [20, 30, 40, 50, 60] and evaluate predictive accuracy on held-out season(s). Metrics:
- Log-loss on match outcomes
- Brier score
- Calibration curve (predicted win% vs actual win%)

Output a comparison table and recommend an optimal K.

**Delivered:** `notebooks/param_sweep.py` tested 1,152 combinations. Best balanced: K=30, HA=65, DR=0.95, PE=1350, SP=500 → log-loss 0.9790, accuracy 54.6%. Results in `notebooks/outputs/param_sweep_results.csv`.

### 3. Extract Elo Engine to `src/elo_engine.py` ✅

**Priority:** P3 | **Impact:** Engineering

Decouple rating logic from plotting/reporting:
- Move `expected_score()`, `elo_update()`, rating loop, and season regression into an `EloEngine` class in `src/elo_engine.py`
- `run_analysis.py` imports and calls the engine, focuses on visualization and reporting
- Enables unit testing and reuse for multi-league work

**Delivered:** `EloEngine` class with methods: `expected_score()`, `mov_multiplier()`, `elo_update()`, `apply_time_decay()`, `compute_ratings()`, `get_rankings()`. Returns `EloResult` dataclass. `run_analysis.py` refactored to use engine. 34 unit tests in `tests/test_elo_engine.py`.

### 4. Full Rankings Table in Output ✅

**Priority:** P3 | **Impact:** Low

Add a complete end-of-period rankings table (all teams, sorted by Elo) to the markdown report output.

**Delivered:** Full 34-team rankings table appended to `epl_elo_analysis.md` via `engine.get_rankings()`.
