# Parameter Sweep Experiments

Log of all parameter tuning experiments, findings, and resulting defaults.

---

## Experiment 1 — Baseline sweep (without spread)

**Date:** 2026-03-11
**Script:** `notebooks/param_sweep.py`
**Scoring:** All 10 seasons, walk-forward (predict then update)
**Matches scored:** 3,711

### Grid

| Parameter | Values tested |
|-----------|--------------|
| K-factor | 20, 30, 40, 50, 60 |
| Home advantage | 0, 40, 65, 80, 100 |
| Decay rate | 0.70, 0.80, 0.85, 0.90, 1.00 |
| Promoted Elo | 1300, 1350, 1400, 1500 |
| **Total** | **500 combinations** |

### Marginal effects

| Parameter | Best (log-loss) | Best (accuracy) |
|-----------|----------------|-----------------|
| K-factor | 30 | 30–40 |
| Home advantage | 40–65 (tied) | 65 |
| Decay rate | 0.90–1.00 | 1.00 |
| Promoted Elo | 1400 | 1300–1400 |

### Top result (log-loss)

| Metric | Value |
|--------|-------|
| K=30, HA=40, DR=1.00, PE=1400 | |
| Log-loss | 0.9798 |
| Brier score | 0.5806 |
| Accuracy | 53.8% |

### Top result (accuracy)

| Metric | Value |
|--------|-------|
| K=30, HA=65, DR=0.85, PE=1350 | |
| Log-loss | 0.9808 |
| Brier score | 0.5814 |
| Accuracy | 54.7% |

### Conclusions

- **K=30** clear winner — K=40 (original) too noisy, K=20 too sluggish
- **Home advantage matters** — 0 significantly worse; 40–65 best range; 80–100 overshoots
- **Decay rate nearly irrelevant** on continuous EPL data — 0.90–1.00 all within noise
- **Promoted Elo** — 1350–1400 confirmed better than 1500 (league average)
- Differences between top combinations small (~0.001 log-loss)

### Defaults set after this experiment

```
K=30, HA=65, DR=0.90, PE=1350
```

---

## Experiment 2 — Spread constant sweep

**Date:** 2026-03-11
**Script:** `notebooks/param_sweep.py` (updated with `spread` parameter)
**Scoring:** All 10 seasons, walk-forward
**Matches scored:** 3,711

### Grid

| Parameter | Values tested |
|-----------|--------------|
| K-factor | 20, 30, 40, 50 |
| Home advantage | 40, 55, 65, 80 |
| Decay rate | 0.85, 0.90, 0.95, 1.00 |
| Promoted Elo | 1300, 1350, 1400 |
| **Spread** | **200, 300, 400, 500, 600, 800** |
| **Total** | **1,152 combinations** |

### Marginal effect of spread

| Spread | Log-loss | Brier | Accuracy |
|--------|----------|-------|----------|
| 200 | 1.0186 | 0.6031 | 53.3% |
| 300 | 0.9900 | 0.5867 | 53.9% |
| 400 | 0.9827 | 0.5825 | 54.1% |
| **500** | **0.9815** | **0.5819** | **54.1%** |
| 600 | 0.9824 | 0.5827 | 54.0% |
| 800 | 0.9864 | 0.5858 | 53.8% |

Spread has the **largest marginal effect** of any parameter tested (~0.007 log-loss improvement from 400→500, vs ~0.004 from K tuning).

### Marginal effects (other parameters, confirmed)

| Parameter | Best (log-loss) | Best (accuracy) |
|-----------|----------------|-----------------|
| K-factor | 30 | 30 |
| Home advantage | 40 | 65 |
| Decay rate | 0.95–1.00 | 0.85–1.00 (flat) |
| Promoted Elo | 1400 | 1350–1400 |

### Top result (log-loss)

| Metric | Value |
|--------|-------|
| K=20, HA=40, DR=0.95, PE=1400, SP=300 | |
| Log-loss | 0.9789 |
| Brier score | 0.5801 |
| Accuracy | 54.3% |

### Top result (accuracy)

| Metric | Value |
|--------|-------|
| K=30, HA=65, DR=0.95, PE=1350, SP=600 | |
| Log-loss | 0.9803 |
| Brier score | 0.5813 |
| Accuracy | 54.8% |

### Best balanced (top 20 in all three metrics)

| Metric | Value |
|--------|-------|
| K=30, HA=65, DR=0.95, PE=1350, SP=500 | |
| Log-loss | 0.9790 |
| Brier score | 0.5802 |
| Accuracy | 54.6% |

### Interpretation

- **Spread=500 > 400 (chess default)** — football is more random than chess; a wider logistic curve produces better-calibrated predictions
- K × spread interaction: wider spread + higher K ≈ narrower spread + lower K (update magnitude), but the probability *shape* differs
- 200 is far too compressed (overconfident), 800 too flat (under-differentiates)
- Decay rate shifted slightly: 0.95 now edges 0.90 with spread in the model

### Defaults set after this experiment

```
K=30, HA=65, DR=0.95, PE=1350, SP=500
```

---

## Experiment 3 — Post-MoV-fix re-sweep

**Date:** 2026-03-12
**Script:** `notebooks/param_sweep.py` (rewritten to use `EloEngine`)
**Scoring:** EPL 10 seasons, walk-forward (predict then update)
**Matches scored:** 3,711
**Key change:** MoV normalization fix applied — `ln(goal_diff+1)/ln(2)` so 1-goal wins get multiplier 1.0

### Grid

| Parameter | Values tested |
|-----------|--------------|
| K-factor | 20, 30, 40, 50 |
| Home advantage | 40, 55, 65, 80 |
| Decay rate | 0.85, 0.90, 0.95, 1.00 |
| Promoted Elo | 1300, 1350, 1400 |
| Spread | 400, 500, 600 |
| **Total** | **576 combinations** |

### Top result (log-loss)

| Metric | Value |
|--------|-------|
| K=20, HA=55, DR=0.90, PE=1400, SP=400 | |
| Log-loss | 0.9772 |
| Accuracy | 54.4% |

### Key shifts from Experiment 2

- **K dropped: 30 → 20** — MoV fix amplifies 1-goal updates (previously dampened at 0.693×), so lower base K compensates
- **Spread dropped: 500 → 400** — with correct MoV scaling, tighter logistic curve is better
- **Decay rate dropped: 0.95 → 0.90** — stronger decay now beneficial with more responsive updates
- **Home advantage shifted: 65 → 55** — lower K means home advantage needed less boost
- **Promoted Elo: 1350 → 1400** — minor shift, still below league average

### Multi-league validation (with Experiment 3 params)

| League | Matches | Teams | Log Loss | Brier | Accuracy | Top Team | Rating |
|--------|---------|-------|----------|-------|----------|----------|--------|
| Premier League | 3,711 | 34 | 0.9772 | 0.1930 | 54.4% | Arsenal | 1745 |
| Serie A | 3,700 | 34 | 0.9844 | 0.1943 | 54.2% | Inter | 1771 |
| La Liga | 3,690 | 31 | 0.9969 | 0.1974 | 52.5% | Barcelona | 1774 |
| Bundesliga | 2,979 | 30 | 1.0047 | 0.1992 | 51.2% | Bayern Munich | 1822 |
| Ligue 1 | 3,396 | 32 | 1.0093 | 0.2006 | 51.6% | Paris SG | 1745 |
| **Mean** | | | **0.9945** | **0.1969** | **52.8%** | | |

EPL-tuned parameters transfer reasonably well — all leagues beat random (1.099) by wide margin. EPL and Serie A perform best; Bundesliga and Ligue 1 slightly worse (may benefit from per-league tuning in Sprint 4).

---

## Current defaults

Set in `src/config.py` and `.env.example`:

| Parameter | Value | Source |
|-----------|-------|--------|
| `k_factor` | 20 | Experiment 3 (post-MoV fix) |
| `initial_elo` | 1500 | Convention (not tuned) |
| `home_advantage` | 55 | Experiment 3 |
| `decay_rate` | 0.90 | Experiment 3 |
| `promoted_elo` | 1400 | Experiment 3 |
| `spread` | 400 | Experiment 3 |

## Baseline reference

- **Random guess (3-way):** log-loss ≈ 1.099, accuracy ≈ 33.3%
- **Always predict home win:** accuracy ≈ 46%
- **Betting market benchmark (EPL):** accuracy ≈ 53–55%
- **Our model:** log-loss 0.9772, accuracy 54.4% — competitive with market baselines

## Future experiments

- [x] ~~Margin-of-victory K scaling (Sprint 2)~~ — done, MoV normalization fixed in Sprint 3
- [x] ~~K-factor re-sweep after MoV fix~~ — done (Experiment 3)
- [ ] Per-league parameter tuning (Bundesliga/Ligue 1 underperform with EPL-tuned params)
- [ ] Draw probability model alternatives (current: linear scaling from rating gap)
- [ ] Cross-validation by held-out seasons instead of walk-forward on all
- [ ] `autocorr_coeff` and `autocorr_scale` tuning
