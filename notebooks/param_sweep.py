"""Parameter sweep for Elo model — walk-forward evaluation.

Tests combinations of K-factor, home advantage, decay rate, and promoted Elo.
Evaluates predictive accuracy using log-loss and Brier score.

For each match the model predicts P(home win), P(draw), P(away win) from
current ratings, then updates ratings. First-season matches are used for
burn-in only (no scoring) since all teams start at the same rating.

Usage:
    uv run python notebooks/param_sweep.py
"""

import os
import sys
import itertools
import warnings

import numpy as np
import pandas as pd

# Add src to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.elo_engine import EloEngine
from src.config import EloSettings

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)

# ---------------------------------------------------------------------------
# Data loading (same as run_analysis.py)
# ---------------------------------------------------------------------------
BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "..", "data", "epl")
OUT_DIR = os.path.join(BASE, "outputs")
os.makedirs(OUT_DIR, exist_ok=True)

frames = []
for season_dir in sorted(os.listdir(DATA_DIR)):
    csv_path = os.path.join(DATA_DIR, season_dir, "E0.csv")
    if os.path.isfile(csv_path):
        df = pd.read_csv(csv_path, low_memory=False)
        df["Season"] = season_dir
        frames.append(df)

data = pd.concat(frames, ignore_index=True)
core_cols = ["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR", "Season"]
data = data[[c for c in core_cols if c in data.columns]].copy()
data["Date"] = pd.to_datetime(data["Date"], dayfirst=True, errors="coerce")
data = data.dropna(subset=["Date", "HomeTeam", "AwayTeam", "FTR"]).sort_values("Date").reset_index(drop=True)

first_season = data["Season"].iloc[0]
print(f"Loaded {len(data)} matches, {data['Season'].nunique()} seasons")
print(f"First season: {first_season} (no burn-in exclusion)\n")


# ---------------------------------------------------------------------------
# Prediction logic
# ---------------------------------------------------------------------------
def predict_probs(
    r_home: float, r_away: float, home_adv: float, spread: float = 400.0,
) -> tuple[float, float, float]:
    """Predict P(H), P(D), P(A) from Elo ratings.

    Uses the Elo expected score as a proxy for combined H+D/2 probability,
    then splits into three outcomes using observed EPL base rates:
      ~46% H, ~27% D, ~27% A (historical EPL averages).

    The draw fraction is modelled as higher when teams are close in rating
    and lower when one team is heavily favoured.
    """
    # Use raw expected score calculation matching engine's logic
    e_home = 1.0 / (1.0 + 10 ** ((r_away - (r_home + home_adv)) / spread))
    e_away = 1.0 - e_home

    # Draw probability peaks when teams are equal, drops for mismatches.
    # Adapted from: p_draw ∝ 1 - |e_home - e_away|, scaled to ~27% baseline
    rating_gap = abs(e_home - e_away)
    p_draw = max(0.05, 0.34 * (1.0 - rating_gap))

    # Distribute remaining probability proportional to expected scores
    remaining = 1.0 - p_draw
    p_home = remaining * e_home
    p_away = remaining * e_away

    return p_home, p_draw, p_away


# ---------------------------------------------------------------------------
# Elo simulation with scoring
# ---------------------------------------------------------------------------
def run_simulation(
    k_factor: float,
    home_adv: float,
    decay_rate: float,
    promoted_elo: float,
    spread: float = 400.0,
    initial_elo: float = 1500.0,
) -> dict:
    """Run full walk-forward Elo simulation, return accuracy metrics."""
    # Create engine with specified parameters
    settings = EloSettings(
        k_factor=k_factor,
        home_advantage=home_adv,
        decay_rate=decay_rate,
        promoted_elo=promoted_elo,
        spread=spread,
        initial_elo=initial_elo,
    )
    engine = EloEngine(settings)

    elo: dict[str, float] = {}
    last_match: dict[str, pd.Timestamp] = {}

    log_losses: list[float] = []
    brier_scores: list[float] = []
    correct: list[bool] = []

    for _, row in data.iterrows():
        home = row["HomeTeam"]
        away = row["AwayTeam"]
        result = row["FTR"]
        date = row["Date"]
        season = row["Season"]
        home_goals = int(row["FTHG"])
        away_goals = int(row["FTAG"])

        # Initialize new teams
        for team in (home, away):
            if team not in elo:
                init_r = initial_elo if season == first_season else promoted_elo
                elo[team] = init_r

        # Time decay (using engine method)
        engine.apply_time_decay(home, date, elo, last_match)
        engine.apply_time_decay(away, date, elo, last_match)

        # Predict BEFORE updating (all seasons scored)
        p_h, p_d, p_a = predict_probs(elo[home], elo[away], home_adv, spread)

        # Actual outcome as one-hot
        if result == "H":
            actual = np.array([1.0, 0.0, 0.0])
            predicted_class = "H" if p_h >= p_d and p_h >= p_a else ("D" if p_d >= p_a else "A")
        elif result == "A":
            actual = np.array([0.0, 0.0, 1.0])
            predicted_class = "A" if p_a >= p_d and p_a >= p_h else ("D" if p_d >= p_h else "H")
        else:
            actual = np.array([0.0, 1.0, 0.0])
            predicted_class = "D" if p_d >= p_h and p_d >= p_a else ("H" if p_h >= p_a else "A")

        probs = np.clip(np.array([p_h, p_d, p_a]), 1e-10, 1.0)
        probs /= probs.sum()

        # Log-loss: -sum(actual * log(prob))
        ll = -np.sum(actual * np.log(probs))
        log_losses.append(ll)

        # Brier score: sum((prob - actual)^2)
        bs = np.sum((probs - actual) ** 2)
        brier_scores.append(bs)

        correct.append(predicted_class == result)

        # Elo update (using engine method)
        new_h, new_a, dh, da = engine.elo_update(
            elo[home], elo[away], result, home_goals, away_goals
        )
        elo[home] = new_h
        elo[away] = new_a
        last_match[home] = date
        last_match[away] = date

    return {
        "log_loss": np.mean(log_losses),
        "brier_score": np.mean(brier_scores),
        "accuracy": np.mean(correct),
        "n_scored": len(log_losses),
    }


# ---------------------------------------------------------------------------
# Parameter grid
# ---------------------------------------------------------------------------
K_VALUES = [20, 30, 40, 50]
HOME_ADV_VALUES = [40, 55, 65, 80]
DECAY_RATE_VALUES = [0.85, 0.90, 0.95, 1.00]
PROMOTED_ELO_VALUES = [1300, 1350, 1400]
SPREAD_VALUES = [400, 500, 600]

grid = list(itertools.product(
    K_VALUES, HOME_ADV_VALUES, DECAY_RATE_VALUES, PROMOTED_ELO_VALUES, SPREAD_VALUES,
))
print(f"Parameter grid: {len(grid)} combinations\n")

# ---------------------------------------------------------------------------
# Run sweep
# ---------------------------------------------------------------------------
results = []
for i, (k, ha, dr, pe, sp) in enumerate(grid):
    metrics = run_simulation(
        k_factor=k, home_adv=ha, decay_rate=dr, promoted_elo=pe, spread=sp,
    )
    results.append({
        "k_factor": k,
        "home_advantage": ha,
        "decay_rate": dr,
        "promoted_elo": pe,
        "spread": sp,
        **metrics,
    })
    if (i + 1) % 50 == 0:
        print(f"  {i + 1}/{len(grid)} done...")

df_results = pd.DataFrame(results).sort_values("log_loss")

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
print("\n" + "=" * 80)
print("TOP 20 COMBINATIONS BY LOG-LOSS")
print("=" * 80)
print(df_results.head(20).to_string(index=False, float_format="%.4f"))

print("\n" + "=" * 80)
print("TOP 20 COMBINATIONS BY BRIER SCORE")
print("=" * 80)
print(df_results.sort_values("brier_score").head(20).to_string(index=False, float_format="%.4f"))

print("\n" + "=" * 80)
print("TOP 20 COMBINATIONS BY ACCURACY")
print("=" * 80)
print(df_results.sort_values("accuracy", ascending=False).head(20).to_string(index=False, float_format="%.4f"))

# Per-parameter marginal analysis
print("\n" + "=" * 80)
print("MARGINAL EFFECT OF EACH PARAMETER (mean log-loss)")
print("=" * 80)
for param in ["k_factor", "home_advantage", "decay_rate", "promoted_elo", "spread"]:
    marginal = df_results.groupby(param).agg(
        log_loss=("log_loss", "mean"),
        brier_score=("brier_score", "mean"),
        accuracy=("accuracy", "mean"),
    ).round(4)
    print(f"\n{param}:")
    print(marginal.to_string())

# Best overall
best = df_results.iloc[0]
print("\n" + "=" * 80)
print("BEST COMBINATION (log-loss)")
print("=" * 80)
print(f"  K-factor:       {best['k_factor']:.0f}")
print(f"  Home advantage: {best['home_advantage']:.0f}")
print(f"  Decay rate:     {best['decay_rate']:.2f}")
print(f"  Promoted Elo:   {best['promoted_elo']:.0f}")
print(f"  Spread:         {best['spread']:.0f}")
print(f"  Log-loss:       {best['log_loss']:.4f}")
print(f"  Brier score:    {best['brier_score']:.4f}")
print(f"  Accuracy:       {best['accuracy']:.1%}")

# Save full results
csv_path = os.path.join(OUT_DIR, "param_sweep_results.csv")
df_results.to_csv(csv_path, index=False)
print(f"\nFull results saved to: {csv_path}")
