#!/usr/bin/env python3
"""Tier weight optimization using Optuna.

Finds data-driven tier weights (T1-T5) by maximizing the log-likelihood
of actual match outcomes given Elo-predicted probabilities.

Uses the display_from_date boundary to separate warm-up (training the
initial ratings) from the evaluation period (measuring prediction quality).

Usage:
    uv run python notebooks/tier_optimization.py
"""

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import optuna
import pandas as pd

from src.config import EloSettings
from src.data_loader import load_all_leagues
from src.elo_engine import EloEngine
from src.european_data import load_european_data
from src.prediction import predict_probs


def load_unified_matches(data_dir: str = "data") -> pd.DataFrame:
    """Load all matches (domestic + European), sorted by date.

    Returns a DataFrame with columns: Date, HomeTeam, AwayTeam, FTHG, FTAG,
    FTR, Season, League, Competition, Tier.
    """
    all_leagues = load_all_leagues(data_dir=data_dir, verbose=False)
    domestic_dfs = []
    for _, df in all_leagues.items():
        df = df.copy()
        df["Tier"] = 5
        df["Competition"] = df["League"]
        domestic_dfs.append(df)
    domestic = pd.concat(domestic_dfs, ignore_index=True)

    european = load_european_data(
        data_dir=str(Path(data_dir) / "european"), verbose=False
    )
    if not european.empty:
        european["League"] = european["Competition"]

    shared_cols = [
        "Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR",
        "Season", "League", "Competition", "Tier",
    ]
    parts = [domestic[shared_cols]]
    if not european.empty:
        parts.append(european[shared_cols])
    unified = pd.concat(parts, ignore_index=True)
    unified = unified.sort_values("Date").reset_index(drop=True)
    return unified


def compute_log_likelihood(
    matches: pd.DataFrame,
    settings: EloSettings,
    eval_from: pd.Timestamp,
) -> tuple[float, int]:
    """Compute ratings on all matches and return log-likelihood on eval period.

    Args:
        matches: All matches sorted by date (including warm-up).
        settings: EloSettings with tier weights to evaluate.
        eval_from: Only evaluate log-likelihood on matches from this date.

    Returns:
        (total_log_likelihood, num_eval_matches)
    """
    engine = EloEngine(settings)
    s = settings

    elo: dict[str, float] = {}
    last_match_date: dict[str, pd.Timestamp] = {}
    first_season = matches["Season"].iloc[0]
    has_tier = "Tier" in matches.columns

    total_ll = 0.0
    n_eval = 0

    for _, row in matches.iterrows():
        home = row["HomeTeam"]
        away = row["AwayTeam"]
        result = row["FTR"]
        date = row["Date"]
        season = row["Season"]
        home_goals = int(row.get("FTHG", 0))
        away_goals = int(row.get("FTAG", 0))
        tier = int(row["Tier"]) if has_tier else 5

        # Initialize new teams
        for team in (home, away):
            if team not in elo:
                init_rating = (
                    s.initial_elo if season == first_season else s.promoted_elo
                )
                elo[team] = init_rating

        # Time decay
        engine.apply_time_decay(home, date, elo, last_match_date)
        engine.apply_time_decay(away, date, elo, last_match_date)

        # Compute predictions BEFORE updating (using current ratings)
        if date >= eval_from:
            e_home = engine.expected_score(
                elo[home] + s.home_advantage, elo[away]
            )
            p_home, p_draw, p_away = predict_probs(e_home)

            # Clamp probabilities to avoid log(0)
            eps = 1e-10
            p_home = max(p_home, eps)
            p_draw = max(p_draw, eps)
            p_away = max(p_away, eps)

            if result == "H":
                total_ll += math.log(p_home)
            elif result == "D":
                total_ll += math.log(p_draw)
            else:
                total_ll += math.log(p_away)
            n_eval += 1

        # Update ratings
        new_h, new_a, _, _ = engine.elo_update(
            elo[home], elo[away], result, home_goals, away_goals, tier
        )
        elo[home] = new_h
        elo[away] = new_a
        last_match_date[home] = date
        last_match_date[away] = date

    return total_ll, n_eval


def create_objective(
    matches: pd.DataFrame,
    eval_from: pd.Timestamp,
):
    """Create an Optuna objective function for tier weight optimization.

    Returns a callable that Optuna will minimize (negative log-likelihood).
    """

    def objective(trial: optuna.Trial) -> float:
        # Sample tier weights with ordering constraints: T1 >= T2 >= T3 >= T4 >= T5=1.0
        t1 = trial.suggest_float("tier_1_weight", 0.5, 3.0)
        t2 = trial.suggest_float("tier_2_weight", 0.5, t1)
        t3 = trial.suggest_float("tier_3_weight", 0.5, t2)
        t4 = trial.suggest_float("tier_4_weight", 0.5, t3)
        # T5 is fixed at 1.0 (domestic baseline)

        # Enforce T4 >= 1.0 (T5)
        if t4 < 1.0:
            # Allow values below 1.0 for T4 — it could be that European group
            # matches are less important. But constrain T4 >= T5 = 1.0.
            # Actually, per task spec, T4 >= T5 = 1.0, so prune if violated.
            raise optuna.TrialPruned()

        settings = EloSettings(
            tier_1_weight=t1,
            tier_2_weight=t2,
            tier_3_weight=t3,
            tier_4_weight=t4,
            tier_5_weight=1.0,
        )

        total_ll, n_eval = compute_log_likelihood(matches, settings, eval_from)

        if n_eval == 0:
            raise optuna.TrialPruned()

        # Return negative log-likelihood (Optuna minimizes)
        return -total_ll

    return objective


def run_optimization(n_trials: int = 150) -> dict:
    """Run the full tier weight optimization.

    Args:
        n_trials: Number of Optuna trials.

    Returns:
        Results dict with best weights, scores, and comparison.
    """
    print("=" * 60)
    print("TIER WEIGHT OPTIMIZATION")
    print("=" * 60)

    # Load data
    print("\nLoading match data...")
    matches = load_unified_matches()
    print(f"  Total matches: {len(matches)}")
    print(f"  Date range: {matches['Date'].min().date()} to {matches['Date'].max().date()}")

    # Tier distribution
    tier_counts = matches["Tier"].value_counts().sort_index()
    print("\n  Tier distribution:")
    tier_labels = {
        1: "CL knockout", 2: "CL group/league", 3: "EL knockout",
        4: "EL group/Conference", 5: "Domestic",
    }
    for tier, count in tier_counts.items():
        label = tier_labels.get(int(tier), f"Tier {tier}")
        print(f"    T{int(tier)} ({label}): {count} matches")

    eval_from = pd.Timestamp("2016-08-01")
    n_eval_matches = len(matches[matches["Date"] >= eval_from])
    print(f"\n  Warm-up period: before {eval_from.date()}")
    print(f"  Evaluation matches: {n_eval_matches}")

    # Baseline: current default weights
    print("\nComputing baseline (current defaults)...")
    baseline_settings = EloSettings()
    baseline_ll, baseline_n = compute_log_likelihood(
        matches, baseline_settings, eval_from
    )
    baseline_avg_ll = baseline_ll / baseline_n
    print(f"  Baseline log-likelihood: {baseline_ll:.2f}")
    print(f"  Baseline avg LL per match: {baseline_avg_ll:.6f}")
    print(f"  Baseline weights: T1={baseline_settings.tier_1_weight}, "
          f"T2={baseline_settings.tier_2_weight}, "
          f"T3={baseline_settings.tier_3_weight}, "
          f"T4={baseline_settings.tier_4_weight}, "
          f"T5={baseline_settings.tier_5_weight}")

    # Run optimization
    print(f"\nRunning Optuna optimization ({n_trials} trials)...")
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    study = optuna.create_study(
        direction="minimize",
        sampler=optuna.samplers.TPESampler(seed=42),
        study_name="tier_weight_optimization",
    )

    objective = create_objective(matches, eval_from)
    study.optimize(objective, n_trials=n_trials, show_progress_bar=True)

    # Results
    best = study.best_params
    best_neg_ll = study.best_value
    best_ll = -best_neg_ll
    best_avg_ll = best_ll / baseline_n

    print(f"\n{'=' * 60}")
    print("OPTIMIZATION RESULTS")
    print(f"{'=' * 60}")
    print(f"\n  Best weights:")
    print(f"    T1 (CL knockout):       {best['tier_1_weight']:.4f}  (was {baseline_settings.tier_1_weight})")
    print(f"    T2 (CL group/league):   {best['tier_2_weight']:.4f}  (was {baseline_settings.tier_2_weight})")
    print(f"    T3 (EL knockout):       {best['tier_3_weight']:.4f}  (was {baseline_settings.tier_3_weight})")
    print(f"    T4 (EL group/Conf):     {best['tier_4_weight']:.4f}  (was {baseline_settings.tier_4_weight})")
    print(f"    T5 (Domestic):          1.0000  (fixed baseline)")

    print(f"\n  Log-likelihood comparison:")
    print(f"    Baseline:  {baseline_ll:.2f} (avg {baseline_avg_ll:.6f}/match)")
    print(f"    Optimized: {best_ll:.2f} (avg {best_avg_ll:.6f}/match)")

    improvement = best_ll - baseline_ll
    improvement_pct = (improvement / abs(baseline_ll)) * 100.0
    print(f"\n  Improvement: {improvement:.2f} ({improvement_pct:+.4f}%)")

    if improvement_pct > 1.0:
        print("\n  ** MEANINGFUL IMPROVEMENT (>1%) — recommend updating defaults **")
    elif improvement_pct > 0.0:
        print("\n  Minor improvement (<1%) — current defaults are reasonable")
    else:
        print("\n  No improvement — current defaults are optimal or near-optimal")

    # Cross-validation: evaluate on different season splits
    print(f"\n{'=' * 60}")
    print("CROSS-VALIDATION")
    print(f"{'=' * 60}")

    cv_splits = [
        ("2016-08-01", "2019-07-31", "2019-08-01", "2026-12-31"),
        ("2016-08-01", "2021-07-31", "2021-08-01", "2026-12-31"),
        ("2016-08-01", "2023-07-31", "2023-08-01", "2026-12-31"),
    ]

    best_settings = EloSettings(
        tier_1_weight=best["tier_1_weight"],
        tier_2_weight=best["tier_2_weight"],
        tier_3_weight=best["tier_3_weight"],
        tier_4_weight=best["tier_4_weight"],
        tier_5_weight=1.0,
    )

    cv_results = []
    for train_start, train_end, val_start, val_end in cv_splits:
        val_from = pd.Timestamp(val_start)
        val_to = pd.Timestamp(val_end)

        # Only evaluate on the validation window
        val_mask = (matches["Date"] >= val_from) & (matches["Date"] <= val_to)
        n_val = val_mask.sum()
        if n_val == 0:
            continue

        # Baseline on this split
        bl_ll, bl_n = compute_log_likelihood(matches, baseline_settings, val_from)
        # Optimized on this split
        opt_ll, opt_n = compute_log_likelihood(matches, best_settings, val_from)

        split_improvement = ((opt_ll - bl_ll) / abs(bl_ll)) * 100.0 if bl_ll != 0 else 0.0
        cv_results.append({
            "validation_period": f"{val_start} to {val_end}",
            "n_matches": bl_n,
            "baseline_ll": round(bl_ll, 2),
            "optimized_ll": round(opt_ll, 2),
            "improvement_pct": round(split_improvement, 4),
        })
        print(f"\n  Val period {val_start} to {val_end} ({bl_n} matches):")
        print(f"    Baseline:  {bl_ll:.2f}")
        print(f"    Optimized: {opt_ll:.2f}")
        print(f"    Change:    {split_improvement:+.4f}%")

    # Save results
    results = {
        "baseline": {
            "tier_1_weight": baseline_settings.tier_1_weight,
            "tier_2_weight": baseline_settings.tier_2_weight,
            "tier_3_weight": baseline_settings.tier_3_weight,
            "tier_4_weight": baseline_settings.tier_4_weight,
            "tier_5_weight": baseline_settings.tier_5_weight,
            "log_likelihood": round(baseline_ll, 4),
            "avg_ll_per_match": round(baseline_avg_ll, 6),
            "n_eval_matches": baseline_n,
        },
        "optimized": {
            "tier_1_weight": round(best["tier_1_weight"], 4),
            "tier_2_weight": round(best["tier_2_weight"], 4),
            "tier_3_weight": round(best["tier_3_weight"], 4),
            "tier_4_weight": round(best["tier_4_weight"], 4),
            "tier_5_weight": 1.0,
            "log_likelihood": round(best_ll, 4),
            "avg_ll_per_match": round(best_avg_ll, 6),
            "n_eval_matches": baseline_n,
        },
        "improvement": {
            "absolute": round(improvement, 4),
            "percentage": round(improvement_pct, 4),
            "meaningful": improvement_pct > 1.0,
        },
        "cross_validation": cv_results,
        "optimization": {
            "n_trials": n_trials,
            "n_completed": len(study.trials),
            "sampler": "TPESampler(seed=42)",
        },
    }

    output_path = Path(__file__).parent / "tier_optimization_results.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n\nResults saved to: {output_path}")

    return results


if __name__ == "__main__":
    run_optimization(n_trials=150)
