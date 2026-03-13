"""Sprint 2 impact analysis — compare sprint-1 baseline vs sprint-2 engine.

Measures the effect of margin-of-victory adjustment on predictive quality
using walk-forward evaluation on 3,711 EPL matches.
"""

import os
import sys
import math
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from src.config import EloSettings
from src.elo_engine import EloEngine

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "..", "data", "epl")

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
data["FTHG"] = pd.to_numeric(data["FTHG"], errors="coerce").fillna(0).astype(int)
data["FTAG"] = pd.to_numeric(data["FTAG"], errors="coerce").fillna(0).astype(int)

print(f"Loaded {len(data)} matches across {data['Season'].nunique()} seasons\n")


# ---------------------------------------------------------------------------
# Walk-forward evaluation function
# ---------------------------------------------------------------------------
def predict_probs(
    e_home: float,
) -> tuple[float, float, float]:
    """Convert expected score into 3-way probabilities."""
    e_away = 1.0 - e_home
    rating_gap = abs(e_home - e_away)
    p_draw = max(0.05, 0.34 * (1.0 - rating_gap))
    remaining = 1.0 - p_draw
    return remaining * e_home, p_draw, remaining * e_away


def evaluate_engine(engine: EloEngine, label: str) -> dict:
    """Walk-forward evaluation returning predictive metrics."""
    s = engine.settings
    elo: dict[str, float] = {}
    last_match: dict[str, pd.Timestamp] = {}
    first_season = data["Season"].iloc[0]

    log_losses, brier_scores, correct = [], [], []
    abs_deltas = []

    for _, row in data.iterrows():
        home, away, result = row["HomeTeam"], row["AwayTeam"], row["FTR"]
        date, season = row["Date"], row["Season"]
        home_goals, away_goals = int(row["FTHG"]), int(row["FTAG"])

        for team in (home, away):
            if team not in elo:
                elo[team] = s.initial_elo if season == first_season else s.promoted_elo

        # Time decay
        engine.apply_time_decay(home, date, elo, last_match)
        engine.apply_time_decay(away, date, elo, last_match)

        # Predict
        e_home = engine.expected_score(elo[home] + s.home_advantage, elo[away])
        p_h, p_d, p_a = predict_probs(e_home)
        probs = np.clip(np.array([p_h, p_d, p_a]), 1e-10, 1.0)
        probs /= probs.sum()

        if result == "H":
            actual = np.array([1.0, 0.0, 0.0])
        elif result == "A":
            actual = np.array([0.0, 0.0, 1.0])
        else:
            actual = np.array([0.0, 1.0, 0.0])

        log_losses.append(-np.sum(actual * np.log(probs)))
        brier_scores.append(np.sum((probs - actual) ** 2))

        pred_class = ["H", "D", "A"][np.argmax(probs)]
        correct.append(pred_class == result)

        # Update
        new_h, new_a, dh, _ = engine.elo_update(
            elo[home], elo[away], result, home_goals, away_goals
        )
        elo[home] = new_h
        elo[away] = new_a
        last_match[home] = date
        last_match[away] = date
        abs_deltas.append(abs(dh))

    rankings = engine.get_rankings(elo)
    elo_spread = rankings[0][1] - rankings[-1][1]

    return {
        "label": label,
        "log_loss": np.mean(log_losses),
        "brier_score": np.mean(brier_scores),
        "accuracy": np.mean(correct),
        "mean_abs_delta": np.mean(abs_deltas),
        "std_abs_delta": np.std(abs_deltas),
        "elo_spread": elo_spread,
        "top_team": rankings[0][0],
        "top_elo": rankings[0][1],
        "bottom_team": rankings[-1][0],
        "bottom_elo": rankings[-1][1],
    }


# ---------------------------------------------------------------------------
# Configurations to compare
# ---------------------------------------------------------------------------
configs = {
    "Sprint 1 (no MoV, K=40)": EloSettings(
        k_factor=40.0, home_advantage=65.0, decay_rate=0.95,
        promoted_elo=1350.0, spread=500.0,
        mov_autocorr_coeff=2.2, mov_autocorr_scale=0.001,
    ),
    "Sprint 1 (tuned, K=30)": EloSettings(
        k_factor=30.0, home_advantage=65.0, decay_rate=0.95,
        promoted_elo=1350.0, spread=500.0,
        mov_autocorr_coeff=2.2, mov_autocorr_scale=0.001,
    ),
    "Sprint 2 (MoV enabled, K=30)": EloSettings(
        k_factor=30.0, home_advantage=65.0, decay_rate=0.95,
        promoted_elo=1350.0, spread=500.0,
        mov_autocorr_coeff=2.2, mov_autocorr_scale=0.001,
    ),
}

# For sprint 1 configs, we need to disable MoV by passing 0 goals
# We'll create special engines that bypass MoV

class NoMoVEngine(EloEngine):
    """Engine that ignores goal difference (sprint 1 behavior)."""
    def elo_update(self, r_home, r_away, result, home_goals=0, away_goals=0):
        return super().elo_update(r_home, r_away, result, 0, 0)


# ---------------------------------------------------------------------------
# Run evaluations
# ---------------------------------------------------------------------------
results = []

# Sprint 1 original (K=40, no MoV)
s1_orig = EloSettings(
    k_factor=40.0, home_advantage=65.0, decay_rate=0.95,
    promoted_elo=1350.0, spread=500.0,
)
results.append(evaluate_engine(NoMoVEngine(s1_orig), "S1: Original (K=40, no MoV)"))

# Sprint 1 tuned (K=30, no MoV)
s1_tuned = EloSettings(
    k_factor=30.0, home_advantage=65.0, decay_rate=0.95,
    promoted_elo=1350.0, spread=500.0,
)
results.append(evaluate_engine(NoMoVEngine(s1_tuned), "S1: Tuned (K=30, no MoV)"))

# Sprint 2 (K=30, MoV enabled)
s2 = EloSettings(
    k_factor=30.0, home_advantage=65.0, decay_rate=0.95,
    promoted_elo=1350.0, spread=500.0,
    mov_autocorr_coeff=2.2, mov_autocorr_scale=0.001,
)
results.append(evaluate_engine(EloEngine(s2), "S2: MoV enabled (K=30)"))

# Sprint 2 with higher base K to compensate for MoV dampening draws
s2_k40 = EloSettings(
    k_factor=40.0, home_advantage=65.0, decay_rate=0.95,
    promoted_elo=1350.0, spread=500.0,
    mov_autocorr_coeff=2.2, mov_autocorr_scale=0.001,
)
results.append(evaluate_engine(EloEngine(s2_k40), "S2: MoV enabled (K=40)"))

# Sprint 2 with K=50
s2_k50 = EloSettings(
    k_factor=50.0, home_advantage=65.0, decay_rate=0.95,
    promoted_elo=1350.0, spread=500.0,
    mov_autocorr_coeff=2.2, mov_autocorr_scale=0.001,
)
results.append(evaluate_engine(EloEngine(s2_k50), "S2: MoV enabled (K=50)"))

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
print("=" * 90)
print("SPRINT 2 IMPACT ANALYSIS — MODEL COMPARISON")
print("=" * 90)
print()

df = pd.DataFrame(results)
cols = ["label", "log_loss", "brier_score", "accuracy", "mean_abs_delta",
        "elo_spread", "top_team", "top_elo", "bottom_team", "bottom_elo"]
print(df[cols].to_string(index=False, float_format="%.4f"))

print("\n")
print("=" * 90)
print("FEATURE IMPACT SUMMARY")
print("=" * 90)

baseline = results[1]  # S1 tuned K=30
for r in results:
    if r["label"] == baseline["label"]:
        continue
    ll_delta = r["log_loss"] - baseline["log_loss"]
    acc_delta = r["accuracy"] - baseline["accuracy"]
    bs_delta = r["brier_score"] - baseline["brier_score"]
    print(f"\n{r['label']} vs S1 Tuned baseline:")
    print(f"  Log-loss:  {ll_delta:+.4f} ({'better' if ll_delta < 0 else 'worse'})")
    print(f"  Brier:     {bs_delta:+.4f} ({'better' if bs_delta < 0 else 'worse'})")
    print(f"  Accuracy:  {acc_delta:+.1%} ({'better' if acc_delta > 0 else 'worse'})")
    print(f"  Elo spread: {r['elo_spread']:.0f} (baseline: {baseline['elo_spread']:.0f})")
