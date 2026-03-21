"""Momentum-blended prediction model validation.

Tests a two-predictor blend:
  P_final = α * P_elo + (1-α) * P_momentum

where P_momentum is derived independently from an EWMA of recent Elo deltas,
converted to 3-way match probabilities via a Davidson-style logistic model.
"""

import sqlite3
from dataclasses import dataclass, field
from itertools import product
from typing import NamedTuple

import numpy as np
import pandas as pd
from sklearn.metrics import log_loss, brier_score_loss

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class MomentumConfig:
    """EWMA momentum parameters."""
    decay_factor: float = 0.85   # λ: exponential decay per match (higher = smoother)
    lookback_window: int = 10    # N: number of past matches to include
    min_matches: int = 3         # require this many matches before computing momentum


@dataclass
class BlendConfig:
    """Parameters for converting momentum → probabilities and blending."""
    mom_spread: float = 20.0     # analogous to Elo spread; converts mom_diff → win prob
    alpha: float = 0.10          # weight on Elo: P_final = α·P_elo + (1-α)·P_momentum
    home_advantage: float = 55.0 # home advantage in Elo points (same as base model)
    draw_steepness: float = 1.0  # controls how sharply draw prob falls with |mom_diff|


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_full_dataset(db_path: str) -> tuple[pd.DataFrame, dict]:
    """Load all predictions + pre-match data from DB.

    Returns:
        (predictions_df, team_histories)
        predictions_df has columns: p_home, p_draw, p_away, home_elo, away_elo,
            result, home_team_id, away_team_id, date, match_id
        team_histories: dict of team_id → DataFrame[date, rating, rating_delta]
    """
    conn = sqlite3.connect(db_path)

    preds = pd.read_sql_query("""
        SELECT
            p.p_home, p.p_draw, p.p_away,
            p.home_elo, p.away_elo,
            m.result,
            m.home_team_id, m.away_team_id,
            m.date,
            m.id AS match_id
        FROM predictions p
        JOIN matches m ON p.match_id = m.id
        WHERE m.date >= '2016-08-01'
          AND p.brier_score IS NOT NULL
        ORDER BY m.date
    """, conn)

    rh = pd.read_sql_query("""
        SELECT team_id, date, rating, rating_delta
        FROM ratings_history
        ORDER BY team_id, date
    """, conn)

    conn.close()

    # Build per-team history lookup
    team_histories: dict[int, pd.DataFrame] = {}
    for tid, grp in rh.groupby("team_id"):
        team_histories[tid] = grp.reset_index(drop=True)

    return preds, team_histories


# ---------------------------------------------------------------------------
# Momentum computation
# ---------------------------------------------------------------------------

def build_momentum_lookup(
    predictions: pd.DataFrame,
    team_histories: dict,
    config: MomentumConfig,
) -> pd.DataFrame:
    """Pre-compute home/away momentum for every row in predictions.

    For each match we want momentum as of the match date, i.e. using only
    Elo deltas from matches BEFORE this date (strict <).

    Args:
        predictions: All prediction rows.
        team_histories: Dict of team_id → history DataFrame.
        config: Momentum parameters.

    Returns:
        predictions with two new columns: home_momentum, away_momentum
    """
    λ = config.decay_factor
    N = config.lookback_window
    min_m = config.min_matches

    # Pre-build per-team numpy arrays for fast slice access
    # team_arrays[tid] = (dates_array, deltas_array)
    team_arrays: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    for tid, hist in team_histories.items():
        dates = hist["date"].values.astype("U10")   # YYYY-MM-DD strings
        deltas = hist["rating_delta"].values.astype(float)
        team_arrays[tid] = (dates, deltas)

    def _momentum(tid: int, match_date: str) -> float:
        if tid not in team_arrays:
            return 0.0
        dates, deltas = team_arrays[tid]
        # Indices of matches strictly before match_date
        mask = dates < match_date
        n_avail = mask.sum()
        if n_avail < min_m:
            return 0.0
        recent = deltas[mask][-N:][::-1]  # most recent first, up to N entries
        k = len(recent)
        w = np.array([λ**i for i in range(k)])
        w /= w.sum()
        return float(w @ recent)

    home_mom = np.empty(len(predictions))
    away_mom = np.empty(len(predictions))

    for i, (_, row) in enumerate(predictions.iterrows()):
        d = row["date"]
        home_mom[i] = _momentum(row["home_team_id"], d)
        away_mom[i] = _momentum(row["away_team_id"], d)

    out = predictions.copy()
    out["home_momentum"] = home_mom
    out["away_momentum"] = away_mom
    return out


# ---------------------------------------------------------------------------
# Probability models
# ---------------------------------------------------------------------------

def momentum_to_probs(
    home_mom: np.ndarray,
    away_mom: np.ndarray,
    cfg: BlendConfig,
) -> np.ndarray:
    """Convert per-match momentum values to 3-way probabilities.

    Model
    -----
    We use a Davidson-style extension of the Bradley-Terry model.

    Let δ = home_momentum + home_advantage - away_momentum  (signed differential)
    The raw win-probability for the home side under logistic:

        p_h_raw = 1 / (1 + 10^(-δ / spread))
        p_a_raw = 1 - p_h_raw

    Draw probability is modelled as a decreasing function of |δ|:

        p_d_unnorm = draw_steepness / (draw_steepness + |δ|)   (Lorentzian kernel)

    These are then re-normalised to sum to 1.

    This gives draws their highest share when both teams are in identical form,
    decreasing continuously as one team's momentum dominates.

    Args:
        home_mom: Array of home-team momentum values.
        away_mom: Array of away-team momentum values.
        cfg: Blend configuration (spread, HA, draw_steepness).

    Returns:
        (n, 3) array of [p_home, p_draw, p_away].
    """
    ha = cfg.home_advantage
    spread = cfg.mom_spread
    steep = cfg.draw_steepness

    delta = (home_mom + ha) - away_mom  # positive → home advantage

    p_h_raw = 1.0 / (1.0 + 10.0 ** (-delta / spread))
    p_a_raw = 1.0 - p_h_raw

    # Draw term: maximum when |delta| ≈ 0, decays with |delta|
    # Lorentzian: steep / (steep + |delta|)
    p_d_raw = steep / (steep + np.abs(delta))

    # Normalise to sum to 1
    total = p_h_raw + p_d_raw + p_a_raw
    p_h = p_h_raw / total
    p_d = p_d_raw / total
    p_a = p_a_raw / total

    return np.column_stack([p_h, p_d, p_a])


def blend_predictions(
    p_elo: np.ndarray,
    p_mom: np.ndarray,
    alpha: float,
) -> np.ndarray:
    """Linear blend of two probability distributions.

    P_final = alpha * P_elo + (1 - alpha) * P_momentum

    Args:
        p_elo: (n, 3) Elo-only probabilities.
        p_mom: (n, 3) Momentum-only probabilities.
        alpha: Weight on Elo (0 = pure momentum, 1 = pure Elo).

    Returns:
        (n, 3) blended probabilities.
    """
    return alpha * p_elo + (1.0 - alpha) * p_mom


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

class EvalResult(NamedTuple):
    log_loss: float
    brier: float


def evaluate(y_true: np.ndarray, y_pred: np.ndarray) -> EvalResult:
    """Compute log-loss and mean Brier score for multi-class predictions."""
    ll = log_loss(y_true, y_pred)
    bs = float(np.mean([
        brier_score_loss(y_true[:, i], y_pred[:, i])
        for i in range(3)
    ]))
    return EvalResult(ll, bs)


# ---------------------------------------------------------------------------
# Grid search
# ---------------------------------------------------------------------------

@dataclass
class GridResult:
    alpha: float
    mom_spread: float
    draw_steepness: float
    log_loss: float
    brier: float
    improvement_pct: float  # vs baseline Elo


def grid_search(
    data: pd.DataFrame,
    mom_config: MomentumConfig,
    baseline_ll: float,
    alphas: list[float] | None = None,
    spreads: list[float] | None = None,
    steepnesses: list[float] | None = None,
) -> list[GridResult]:
    """Exhaustive grid search over blend parameters.

    Args:
        data: DataFrame with p_home/p_draw/p_away and home/away_momentum columns.
        mom_config: Momentum config (already applied, included for logging).
        baseline_ll: Elo-only log-loss for comparison.
        alphas: Elo blend weights to test.
        spreads: Momentum spread values to test.
        steepnesses: Draw decay steepness values to test.

    Returns:
        List of GridResult sorted by log_loss ascending (best first).
    """
    if alphas is None:
        alphas = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 0.65, 0.80]
    if spreads is None:
        spreads = [5.0, 10.0, 20.0, 30.0, 50.0, 100.0]
    if steepnesses is None:
        steepnesses = [2.0, 5.0, 10.0, 20.0]

    result_map = {"H": [1, 0, 0], "D": [0, 1, 0], "A": [0, 0, 1]}
    y_true = np.array([result_map[r] for r in data["result"]])
    p_elo = data[["p_home", "p_draw", "p_away"]].values
    home_mom = data["home_momentum"].values
    away_mom = data["away_momentum"].values

    total = len(alphas) * len(spreads) * len(steepnesses)
    print(f"  Running {total} parameter combinations...")

    results: list[GridResult] = []

    for spread, steep, alpha in product(spreads, steepnesses, alphas):
        cfg = BlendConfig(
            mom_spread=spread,
            alpha=alpha,
            draw_steepness=steep,
        )
        p_mom = momentum_to_probs(home_mom, away_mom, cfg)
        p_blend = blend_predictions(p_elo, p_mom, alpha)

        ev = evaluate(y_true, p_blend)
        imp = (baseline_ll - ev.log_loss) / baseline_ll * 100.0

        results.append(GridResult(
            alpha=alpha,
            mom_spread=spread,
            draw_steepness=steep,
            log_loss=ev.log_loss,
            brier=ev.brier,
            improvement_pct=imp,
        ))

    results.sort(key=lambda r: r.log_loss)
    return results


# ---------------------------------------------------------------------------
# Full validation pipeline
# ---------------------------------------------------------------------------

def run_blend_validation(
    db_path: str,
    mom_config: MomentumConfig | None = None,
) -> dict:
    """End-to-end validation of the momentum blend model.

    Runs the full dataset (all scored backfill predictions from display period).
    Uses pre-computed momentum for speed.

    Returns:
        Dict with baseline stats, best grid result, and top-10 results.
    """
    if mom_config is None:
        mom_config = MomentumConfig(decay_factor=0.85, lookback_window=10)

    print(f"\nMomentum config: λ={mom_config.decay_factor}, "
          f"N={mom_config.lookback_window}, min={mom_config.min_matches}")

    # --- Load ---
    print("Loading dataset...")
    preds, team_histories = load_full_dataset(db_path)
    print(f"  {len(preds):,} predictions, {len(team_histories)} teams")

    # --- Baseline ---
    result_map = {"H": [1, 0, 0], "D": [0, 1, 0], "A": [0, 0, 1]}
    y_true = np.array([result_map[r] for r in preds["result"]])
    p_elo = preds[["p_home", "p_draw", "p_away"]].values

    baseline = evaluate(y_true, p_elo)
    print(f"\nBaseline (Elo only):")
    print(f"  Log-Loss: {baseline.log_loss:.6f}")
    print(f"  Brier:    {baseline.brier:.6f}")

    # Draw rate statistics
    draw_rate = (preds["result"] == "D").mean()
    home_win_rate = (preds["result"] == "H").mean()
    away_win_rate = (preds["result"] == "A").mean()
    print(f"\nHistorical outcome rates:")
    print(f"  Home win: {home_win_rate:.3f}")
    print(f"  Draw:     {draw_rate:.3f}")
    print(f"  Away win: {away_win_rate:.3f}")

    # --- Momentum ---
    print("\nComputing pre-match momentum...")
    data = build_momentum_lookup(preds, team_histories, mom_config)

    # Diagnostics
    home_mom = data["home_momentum"]
    away_mom = data["away_momentum"]
    print(f"\nMomentum statistics:")
    print(f"  Home: mean={home_mom.mean():+.2f}, std={home_mom.std():.2f}, "
          f"range=[{home_mom.min():.1f}, {home_mom.max():.1f}]")
    print(f"  Away: mean={away_mom.mean():+.2f}, std={away_mom.std():.2f}, "
          f"range=[{away_mom.min():.1f}, {away_mom.max():.1f}]")

    # Sanity check: momentum differential direction
    mom_diff = home_mom - away_mom
    for outcome, label in [("H", "Home wins"), ("D", "Draws"), ("A", "Away wins")]:
        mask = preds["result"] == outcome
        avg_diff = mom_diff[mask].mean()
        expected = "> 0" if outcome == "H" else "≈ 0" if outcome == "D" else "< 0"
        print(f"  {label}: avg(mom_diff)={avg_diff:+.3f} (expected {expected})")

    # Preview: what do pure-momentum probs look like at various spreads?
    print("\nMomentum-only probability preview (sample spread values):")
    for spread in [10.0, 30.0, 100.0]:
        cfg = BlendConfig(mom_spread=spread, draw_steepness=5.0)
        p_mom = momentum_to_probs(home_mom.values, away_mom.values, cfg)
        p_mom_ev = evaluate(y_true, p_mom)
        print(f"  Pure momentum (spread={spread:5.0f}): "
              f"LL={p_mom_ev.log_loss:.6f}, Brier={p_mom_ev.brier:.6f}")

    # --- Grid search ---
    print("\nGrid search over blend parameters...")
    grid_results = grid_search(data, mom_config, baseline.log_loss)

    # --- Results ---
    best = grid_results[0]
    print(f"\n{'='*65}")
    print(f"TOP 10 PARAMETER COMBINATIONS (by log-loss)")
    print(f"{'='*65}")
    print(f"{'α':>6} {'spread':>8} {'steep':>7}  {'LL':>10}  {'Brier':>8}  {'Δ%':>8}")
    print(f"{'-'*65}")
    for r in grid_results[:10]:
        print(f"{r.alpha:6.2f} {r.mom_spread:8.1f} {r.draw_steepness:7.1f}  "
              f"{r.log_loss:10.6f}  {r.brier:8.6f}  {r.improvement_pct:+8.4f}%")

    print(f"\n{'='*65}")
    print(f"BEST RESULT")
    print(f"{'='*65}")
    print(f"  α (Elo weight):    {best.alpha}")
    print(f"  Momentum spread:   {best.mom_spread}")
    print(f"  Draw steepness:    {best.draw_steepness}")
    print(f"  Log-Loss:          {best.log_loss:.6f}  (baseline: {baseline.log_loss:.6f})")
    print(f"  Brier:             {best.brier:.6f}  (baseline: {baseline.brier:.6f})")
    print(f"  Improvement:       {best.improvement_pct:+.4f}%")

    verdict = (
        "YES — meaningful improvement"
        if best.improvement_pct > 0.1
        else "MARGINAL — improvement below noise floor"
        if best.improvement_pct > 0
        else "NO — momentum degrades predictions even as a separate predictor"
    )
    print(f"\nConclusion: {verdict}")

    # Also test pure momentum baseline to understand its predictive floor
    best_pure_spread = min(
        [10.0, 30.0, 100.0],
        key=lambda s: evaluate(
            y_true,
            momentum_to_probs(
                home_mom.values, away_mom.values,
                BlendConfig(mom_spread=s, draw_steepness=5.0)
            )
        ).log_loss
    )
    p_mom_best = momentum_to_probs(
        home_mom.values, away_mom.values,
        BlendConfig(mom_spread=best_pure_spread, draw_steepness=5.0),
    )
    pure_mom_ev = evaluate(y_true, p_mom_best)
    print(f"\nPure momentum predictor (best spread={best_pure_spread}):")
    print(f"  LL={pure_mom_ev.log_loss:.6f} vs Elo baseline {baseline.log_loss:.6f}")
    print(f"  → Momentum alone is "
          f"{'better' if pure_mom_ev.log_loss < baseline.log_loss else 'worse'} "
          f"than Elo in isolation.")

    return {
        "n_predictions": len(preds),
        "mom_config": mom_config,
        "baseline_log_loss": baseline.log_loss,
        "baseline_brier": baseline.brier,
        "best": best,
        "top10": grid_results[:10],
        "all_results": grid_results,
    }


# ---------------------------------------------------------------------------
# Multi-momentum-config sweep
# ---------------------------------------------------------------------------

def sweep_momentum_configs(db_path: str) -> None:
    """Test blended model across several momentum configurations."""
    configs = [
        MomentumConfig(decay_factor=0.70, lookback_window=5, min_matches=3),
        MomentumConfig(decay_factor=0.85, lookback_window=10, min_matches=3),
        MomentumConfig(decay_factor=0.95, lookback_window=15, min_matches=5),
    ]

    print("=" * 65)
    print("MOMENTUM-BLEND MODEL: MULTI-CONFIG SWEEP")
    print("=" * 65)

    sweep_results = []
    for cfg in configs:
        r = run_blend_validation(db_path, cfg)
        sweep_results.append(r)

    print(f"\n{'='*65}")
    print("SWEEP SUMMARY")
    print(f"{'='*65}")
    print(f"{'λ':>6} {'N':>4}  {'baseline LL':>12}  {'best LL':>10}  {'improvement':>12}")
    for r in sweep_results:
        mc = r["mom_config"]
        print(f"{mc.decay_factor:6.2f} {mc.lookback_window:4d}  "
              f"{r['baseline_log_loss']:12.6f}  "
              f"{r['best'].log_loss:10.6f}  "
              f"{r['best'].improvement_pct:+12.4f}%")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    DB = "/home/linards/Documents/Private/football-elo/data/elo.db"
    sweep_momentum_configs(DB)
