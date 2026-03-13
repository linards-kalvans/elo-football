# Sprint 1 — Elo Engine Improvements

**Target file:** `notebooks/run_analysis.py` (lines 96–141)
**Goal:** Improve model accuracy with home advantage, season regression, promoted team handling, and parameterization.

---

## Items

### 1. Home Advantage Modifier

**Priority:** P1 | **Impact:** High

EPL home win rate is ~46%, but the model treats home and away symmetrically. Add a home advantage offset to the expected score calculation.

**Change:**
- Add `HOME_ADVANTAGE = 65` constant
- Modify the `elo_update` call to use `expected_score(r_home + HOME_ADVANTAGE, r_away)`
- The offset inflates the home team's expected score without changing stored ratings

**Reference:** FiveThirtyEight uses ~65 points; World Football Elo Ratings uses ~100. Start at 65, tune later.

---

### 2. Continuous Time Decay

**Priority:** P1 | **Impact:** High

Ratings currently carry over unchanged regardless of time elapsed. This ignores squad turnover, form changes, and the natural staleness of old results.

**Change:**
- Before each match, decay both teams' ratings toward `INITIAL_ELO` based on days elapsed since their last match:
  ```python
  days = (current_date - last_match_date[team]).days
  decay = decay_rate ** (days / 365.0)
  elo[team] = decay * elo[team] + (1 - decay) * INITIAL_ELO
  ```
- Default `DECAY_RATE = 0.85` — after a full year of inactivity, retain 85% of earned deviation from 1500
- Track `last_match_date` per team, updated after each match
- This naturally handles season breaks (~2 months → mild pull toward mean), mid-season breaks, and long absences due to relegation

**Tradeoff:** Lower decay rate = more aggressive regression, more reactive to recent form but loses historical signal. Higher = more stable but slower to reflect squad changes. Needs empirical tuning.

**Advantages over season-boundary regression:**
- No need to detect season boundaries or rely on the `Season` column
- Proportional — a 2-month summer break decays less than a 1-year relegation absence
- Works naturally for cross-league and European competition schedules (Sprint 3)

---

### 3. Promoted Team Initialization

**Priority:** P1 | **Impact:** Medium

New teams entering the EPL start at 1500 (league average), but promoted teams are historically weaker — ~40% are relegated in their first season back.

**Change:**
- Add `PROMOTED_ELO = 1350` constant
- When a team first appears after season 1, initialize at `PROMOTED_ELO` instead of `INITIAL_ELO`
- First-season teams (the initial batch) still start at `INITIAL_ELO`

**Note:** This is a heuristic. A future improvement would inherit ratings from Championship data.

---

### 4. Parameterize Constants via `pydantic-settings`

**Priority:** P3 | **Impact:** Low (enables future tuning)

Hardcoded constants make parameter sweeps tedious.

**Change:**
- Add `pydantic-settings` dependency: `uv add pydantic-settings`
- Create `src/config.py` with a `EloSettings(BaseSettings)` class:
  ```python
  from pydantic_settings import BaseSettings

  class EloSettings(BaseSettings):
      k_factor: float = 40.0
      initial_elo: float = 1500.0
      home_advantage: float = 65.0
      decay_rate: float = 0.85
      promoted_elo: float = 1350.0

      model_config = SettingsConfigDict(
          env_file=".env",
          env_prefix="ELO_",
      )
  ```
- Create `.env` at project root with defaults:
  ```
  ELO_K_FACTOR=40
  ELO_INITIAL_ELO=1500
  ELO_HOME_ADVANTAGE=65
  ELO_DECAY_RATE=0.85
  ELO_PROMOTED_ELO=1350
  ```
- Add `.env` to `.gitignore`, commit a `.env.example` with the same defaults
- Replace hardcoded constants in `run_analysis.py` with `settings = EloSettings()` and reference `settings.k_factor`, etc.
- Print active settings at script start for reproducibility

**Usage:** Override any parameter by editing `.env` or setting env vars directly:
```bash
ELO_K_FACTOR=30 ELO_HOME_ADVANTAGE=80 uv run python notebooks/run_analysis.py
```

---

## Acceptance Criteria

- [ ] Script runs end-to-end with `uv run python notebooks/run_analysis.py`
- [ ] Elo trajectory plot visibly reflects home advantage (slight upward bias for home-heavy clubs disappears)
- [ ] Season boundaries produce visible rating compression in the trajectory plot
- [ ] Newly promoted teams start below 1500
- [ ] All four parameters controllable via `.env` file or environment variables (prefixed `ELO_`)
- [ ] Existing outputs (3 figures + markdown report) still generated correctly
- [ ] Parameters table in output markdown reflects actual values used

## Out of Scope

- Margin-of-victory adjustment (Sprint 2)
- K-factor tuning / backtesting (Sprint 2)
- Extracting Elo engine to `src/elo_engine.py` (Sprint 2)
- Competition tier weighting, cross-league calibration (future)
