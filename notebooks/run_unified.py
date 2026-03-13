#!/usr/bin/env python3
"""Unified cross-league Elo calibration with European competition data.

Merges 5 domestic leagues + CL/EL/Conference League into a single rating pool.
European cup matches serve as bridge matches that naturally calibrate teams
across leagues.

Produces:
- Global rankings across all leagues
- Per-league accuracy comparison (domestic-only vs unified)
- CL/EL prediction accuracy
- Top-10 global Elo trajectory plot
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.metrics import log_loss

from src.elo_engine import EloEngine
from src.config import EloSettings
from src.data_loader import load_all_leagues
from src.european_data import load_european_data


def predict_probs(e_home: float) -> tuple[float, float, float]:
    """Predict match outcome probabilities from home expected score."""
    e_away = 1.0 - e_home
    rating_gap = abs(e_home - e_away)
    p_draw = max(0.05, 0.34 * (1.0 - rating_gap))
    remaining = 1.0 - p_draw
    return remaining * e_home, p_draw, remaining * e_away


def build_unified_dataset() -> pd.DataFrame:
    """Load and merge domestic + European data into a single DataFrame."""
    print("Loading domestic league data...")
    all_leagues = load_all_leagues(verbose=False)
    domestic_dfs = []
    for league_id, df in all_leagues.items():
        df = df.copy()
        df["Tier"] = 5  # Domestic = tier 5
        df["Competition"] = df["League"]
        domestic_dfs.append(df)

    domestic = pd.concat(domestic_dfs, ignore_index=True)
    print(f"  Domestic: {len(domestic)} matches across {len(all_leagues)} leagues")

    print("Loading European competition data...")
    european = load_european_data(verbose=False)
    if european.empty:
        print("  WARNING: No European data found!")
        return domestic.sort_values("Date").reset_index(drop=True)

    # Align columns — European data doesn't have League column
    european["League"] = european["Competition"]

    print(f"  European: {len(european)} matches")

    # Merge
    shared_cols = ["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR",
                   "Season", "League", "Competition", "Tier"]
    unified = pd.concat([domestic[shared_cols], european[shared_cols]], ignore_index=True)
    unified = unified.sort_values("Date").reset_index(drop=True)

    print(f"\n  Unified dataset: {len(unified)} matches")
    print(f"  Date range: {unified['Date'].min().date()} to {unified['Date'].max().date()}")
    return unified


def walk_forward_evaluate(matches: pd.DataFrame, settings: EloSettings,
                          label: str = "") -> tuple[dict[str, float], dict[str, list]]:
    """Run walk-forward Elo with per-match predictions.

    Returns:
        (elo_ratings, history) plus prints metrics.
    """
    engine = EloEngine(settings)
    elo: dict[str, float] = {}
    last_match_date: dict[str, pd.Timestamp] = {}
    history: dict[str, list[tuple[pd.Timestamp, float]]] = {}
    first_season = matches["Season"].iloc[0]
    has_tier = "Tier" in matches.columns

    predictions = []
    actuals = []

    for _, row in matches.iterrows():
        home = row["HomeTeam"]
        away = row["AwayTeam"]
        result = row["FTR"]
        date = row["Date"]
        season = row["Season"]
        home_goals = int(row.get("FTHG", 0))
        away_goals = int(row.get("FTAG", 0))
        tier = int(row["Tier"]) if has_tier else 5

        for team in (home, away):
            if team not in elo:
                init = settings.initial_elo if season == first_season else settings.promoted_elo
                elo[team] = init
                history[team] = [(date, init)]

        engine.apply_time_decay(home, date, elo, last_match_date)
        engine.apply_time_decay(away, date, elo, last_match_date)

        # Predict before update
        exp_home = engine.expected_score(elo[home] + settings.home_advantage, elo[away])
        p_h, p_d, p_a = predict_probs(exp_home)
        predictions.append([p_h, p_d, p_a])
        actuals.append(result)

        # Update
        new_h, new_a, _, _ = engine.elo_update(
            elo[home], elo[away], result, home_goals, away_goals, tier
        )
        elo[home] = new_h
        elo[away] = new_a
        last_match_date[home] = date
        last_match_date[away] = date
        history[home].append((date, new_h))
        history[away].append((date, new_a))

    # Compute metrics
    y_pred = np.array(predictions)
    outcome_map = {"H": [1, 0, 0], "D": [0, 1, 0], "A": [0, 0, 1]}
    y_true = np.array([outcome_map[r] for r in actuals])

    ll = log_loss(y_true, y_pred)
    predicted = np.argmax(y_pred, axis=1)
    actual = np.argmax(y_true, axis=1)
    acc = (predicted == actual).mean()

    if label:
        print(f"\n  {label}:")
    print(f"    Log Loss: {ll:.4f}  |  Accuracy: {acc:.3f}  |  Matches: {len(matches)}")

    return elo, history


def main():
    """Run unified cross-league calibration."""
    print("=" * 70)
    print("UNIFIED CROSS-LEAGUE ELO CALIBRATION")
    print("=" * 70)

    settings = EloSettings()
    print(f"\nSettings: K={settings.k_factor}, HA={settings.home_advantage}, "
          f"DR={settings.decay_rate}, SP={settings.spread}")
    print(f"Tier weights: T1={settings.tier_1_weight}, T2={settings.tier_2_weight}, "
          f"T3={settings.tier_3_weight}, T4={settings.tier_4_weight}, T5={settings.tier_5_weight}")

    # Build unified dataset
    print(f"\n{'─'*70}")
    unified = build_unified_dataset()

    # --- Run 1: Domestic-only baselines (per-league) ---
    print(f"\n{'─'*70}")
    print("BASELINE: Per-league domestic-only ratings")
    print(f"{'─'*70}")

    domestic_only = unified[unified["Tier"] == 5]
    league_names = domestic_only["League"].unique()

    baseline_ratings = {}
    for league in sorted(league_names):
        league_df = domestic_only[domestic_only["League"] == league].reset_index(drop=True)
        elo, _ = walk_forward_evaluate(league_df, settings, label=league)
        baseline_ratings[league] = elo

    # --- Run 2: Unified ratings ---
    print(f"\n{'─'*70}")
    print("UNIFIED: All matches (domestic + European) in single rating pool")
    print(f"{'─'*70}")

    unified_elo, unified_history = walk_forward_evaluate(unified, settings, label="All matches")

    # European-only accuracy
    european_mask = unified["Tier"].isin([1, 2, 3, 4])
    eu_matches = unified[european_mask].reset_index(drop=True)
    if not eu_matches.empty:
        print(f"\n  European matches breakdown:")
        for comp in eu_matches["Competition"].unique():
            comp_df = eu_matches[eu_matches["Competition"] == comp]
            print(f"    {comp}: {len(comp_df)} matches")

    # --- Global Rankings ---
    print(f"\n{'─'*70}")
    print("GLOBAL RANKINGS (Top 30)")
    print(f"{'─'*70}\n")

    engine = EloEngine(settings)
    rankings = engine.get_rankings(unified_elo)

    # Determine league for each team
    team_league = {}
    for _, row in unified.iterrows():
        if row["Tier"] == 5:
            team_league[row["HomeTeam"]] = row["League"]
            team_league[row["AwayTeam"]] = row["League"]

    print(f"{'Rank':>4}  {'Team':<25}  {'Rating':>7}  {'League':<20}")
    print("─" * 62)
    for i, (team, rating) in enumerate(rankings[:30], 1):
        league = team_league.get(team, "European only")
        print(f"{i:4d}  {team:<25}  {rating:7.0f}  {league:<20}")

    # --- Comparison: baseline vs unified for domestic teams ---
    print(f"\n{'─'*70}")
    print("CALIBRATION IMPACT: Domestic-only vs Unified ratings")
    print(f"{'─'*70}\n")

    print(f"{'League':<20}  {'Team':<20}  {'Domestic':>9}  {'Unified':>9}  {'Delta':>7}")
    print("─" * 72)

    for league in sorted(league_names):
        if league not in baseline_ratings:
            continue
        bl = baseline_ratings[league]
        # Top 3 teams per league
        top_domestic = sorted(bl.items(), key=lambda x: -x[1])[:3]
        for team, dom_rating in top_domestic:
            uni_rating = unified_elo.get(team, 0)
            delta = uni_rating - dom_rating
            print(f"{league:<20}  {team:<20}  {dom_rating:9.0f}  {uni_rating:9.0f}  {delta:+7.0f}")
        print()

    # --- Save outputs ---
    output_dir = Path(__file__).parent / "outputs" / "unified"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Rankings CSV
    rankings_df = pd.DataFrame(rankings, columns=["Team", "Rating"])
    rankings_df["League"] = rankings_df["Team"].map(lambda t: team_league.get(t, "European only"))
    rankings_df.to_csv(output_dir / "global_rankings.csv", index=False)

    # Top-10 trajectory plot
    top_10_teams = [t for t, _ in rankings[:10]]
    fig, ax = plt.subplots(figsize=(14, 8))

    for team in top_10_teams:
        if team in unified_history:
            dates = [d for d, _ in unified_history[team]]
            ratings = [r for _, r in unified_history[team]]
            ax.plot(dates, ratings, label=team, linewidth=2, alpha=0.8)

    ax.set_xlabel("Date", fontsize=12)
    ax.set_ylabel("Elo Rating", fontsize=12)
    ax.set_title("Top 10 Global Elo Trajectories (Unified Ratings)", fontsize=14, fontweight="bold")
    ax.legend(loc="best", fontsize=9)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_dir / "global_trajectories.png", dpi=150)
    plt.close()
    print(f"\nOutputs saved to: {output_dir}")

    # --- Summary ---
    print(f"\n{'='*70}")
    print("SPRINT 4 SUMMARY")
    print(f"{'='*70}")
    print(f"  Data sources: 5 domestic leagues + CL/EL/Conference League")
    print(f"  Total matches: {len(unified)}")
    print(f"    Domestic: {len(domestic_only)}")
    print(f"    European: {len(eu_matches)}")
    print(f"  Teams rated: {len(unified_elo)}")
    print(f"  Tier weighting: T1={settings.tier_1_weight}x, T2={settings.tier_2_weight}x, "
          f"T3={settings.tier_3_weight}x, T4/T5=1.0x")
    print(f"  Top team: {rankings[0][0]} ({rankings[0][1]:.0f})")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
