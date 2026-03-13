#!/usr/bin/env python3
"""Multi-league Elo analysis script.

Runs EloEngine independently on each of 5 European leagues and produces:
- Rankings tables
- Elo trajectory plots
- Walk-forward predictive accuracy metrics
- Cross-league comparison table
"""

import sys
from pathlib import Path

# Allow imports from src/
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.metrics import log_loss, brier_score_loss

from src.elo_engine import EloEngine
from src.config import EloSettings
from src.data_loader import load_all_leagues, get_league_info, LEAGUE_CONFIG


def predict_probs(e_home: float) -> tuple[float, float, float]:
    """Predict match outcome probabilities from home expected score.

    Args:
        e_home: Expected score for home team (0-1)

    Returns:
        Tuple of (p_home_win, p_draw, p_away_win)
    """
    e_away = 1.0 - e_home
    rating_gap = abs(e_home - e_away)
    p_draw = max(0.05, 0.34 * (1.0 - rating_gap))
    remaining = 1.0 - p_draw
    return remaining * e_home, p_draw, remaining * e_away


def evaluate_predictions(df: pd.DataFrame) -> dict:
    """Calculate walk-forward predictive metrics.

    Args:
        df: DataFrame with columns p_home, p_draw, p_away, FTR

    Returns:
        Dict with log_loss, brier, accuracy
    """
    # Create one-hot encoded outcomes
    y_true = pd.get_dummies(df['FTR'])[['H', 'D', 'A']].values
    y_pred = df[['p_home', 'p_draw', 'p_away']].values

    # Metrics
    ll = log_loss(y_true, y_pred)
    brier = brier_score_loss(y_true.ravel(), y_pred.ravel())

    # Accuracy: predicted outcome = argmax of probabilities
    predicted_outcomes = np.argmax(y_pred, axis=1)
    actual_outcomes = np.argmax(y_true, axis=1)
    accuracy = (predicted_outcomes == actual_outcomes).mean()

    return {
        'log_loss': ll,
        'brier': brier,
        'accuracy': accuracy
    }


def plot_elo_trajectories(df: pd.DataFrame, league_name: str,
                          output_dir: Path) -> None:
    """Plot Elo trajectories for top 6 teams by final rating.

    Args:
        df: Match dataframe with Elo ratings
        league_name: Name of league for plot title
        output_dir: Directory to save plot
    """
    # Get final ratings for all teams
    final_ratings = {}
    for _, row in df.iterrows():
        final_ratings[row['HomeTeam']] = row['rating_home_after']
        final_ratings[row['AwayTeam']] = row['rating_away_after']

    # Get top 6 teams
    top_teams = sorted(final_ratings.items(), key=lambda x: x[1], reverse=True)[:6]
    top_team_names = [t[0] for t in top_teams]

    # Prepare trajectory data
    fig, ax = plt.subplots(figsize=(12, 7))

    for team in top_team_names:
        # Collect all ratings for this team
        home_matches = df[df['HomeTeam'] == team][['Date', 'rating_home_after']].copy()
        home_matches.columns = ['Date', 'Rating']

        away_matches = df[df['AwayTeam'] == team][['Date', 'rating_away_after']].copy()
        away_matches.columns = ['Date', 'Rating']

        team_ratings = pd.concat([home_matches, away_matches]).sort_values('Date')

        ax.plot(team_ratings['Date'], team_ratings['Rating'],
                label=team, linewidth=2, alpha=0.8)

    ax.set_xlabel('Date', fontsize=12)
    ax.set_ylabel('Elo Rating', fontsize=12)
    ax.set_title(f'{league_name} - Top 6 Teams Elo Trajectories', fontsize=14, fontweight='bold')
    ax.legend(loc='best', fontsize=10)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    output_path = output_dir / 'elo_trajectories.png'
    plt.savefig(output_path, dpi=150)
    plt.close()
    print(f"  Saved trajectory plot: {output_path}")


def analyze_league(league_id: str, df: pd.DataFrame, settings: EloSettings,
                   output_dir: Path) -> dict:
    """Run full Elo analysis on a single league.

    Args:
        league_id: League identifier (e.g., 'epl')
        df: Match dataframe
        settings: EloSettings instance
        output_dir: Output directory for this league

    Returns:
        Dict with metrics and summary stats
    """
    league_info = get_league_info(league_id)
    league_name = league_info['name']

    print(f"\n{'='*60}")
    print(f"Analyzing: {league_name}")
    print(f"{'='*60}")
    print(f"  Matches: {len(df)}")
    print(f"  Seasons: {df['Season'].nunique()}")
    print(f"  Teams: {len(set(df['HomeTeam']) | set(df['AwayTeam']))}")

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize engine
    engine = EloEngine(settings)

    # Walk-forward predictions: process one match at a time
    predictions = []
    ratings_before = []
    ratings_after = []

    # Track state for incremental computation
    elo: dict[str, float] = {}
    last_match_date: dict[str, pd.Timestamp] = {}
    history: dict[str, list[tuple[pd.Timestamp, float]]] = {}
    first_season = df["Season"].iloc[0]

    for idx, row in df.iterrows():
        home = row["HomeTeam"]
        away = row["AwayTeam"]
        result = row["FTR"]
        date = row["Date"]
        season = row["Season"]
        home_goals = int(row.get("FTHG", 0))
        away_goals = int(row.get("FTAG", 0))

        # Initialize new teams
        for team in (home, away):
            if team not in elo:
                init_rating = (
                    settings.initial_elo if season == first_season else settings.promoted_elo
                )
                elo[team] = init_rating
                history[team] = [(date, init_rating)]

        # Time decay
        engine.apply_time_decay(home, date, elo, last_match_date)
        engine.apply_time_decay(away, date, elo, last_match_date)

        # Get ratings before update
        rating_home_before = elo[home]
        rating_away_before = elo[away]
        ratings_before.append({
            'rating_home_before': rating_home_before,
            'rating_away_before': rating_away_before
        })

        # Predict probabilities using ratings before update
        exp_home = engine.expected_score(
            rating_home_before + settings.home_advantage,
            rating_away_before
        )
        p_home, p_draw, p_away = predict_probs(exp_home)
        predictions.append({
            'p_home': p_home,
            'p_draw': p_draw,
            'p_away': p_away
        })

        # Update ratings
        new_h, new_a, dh, da = engine.elo_update(
            elo[home], elo[away], result, home_goals, away_goals
        )
        elo[home] = new_h
        elo[away] = new_a
        last_match_date[home] = date
        last_match_date[away] = date
        history[home].append((date, new_h))
        history[away].append((date, new_a))

        ratings_after.append({
            'rating_home_after': new_h,
            'rating_away_after': new_a
        })

    # Combine dataframes
    df_with_preds = df.copy()
    df_with_preds = pd.concat([
        df_with_preds,
        pd.DataFrame(predictions),
        pd.DataFrame(ratings_before),
        pd.DataFrame(ratings_after)
    ], axis=1)

    # Evaluate predictions
    metrics = evaluate_predictions(df_with_preds)
    print(f"\n  Predictive Performance:")
    print(f"    Log Loss:  {metrics['log_loss']:.4f}")
    print(f"    Brier:     {metrics['brier']:.4f}")
    print(f"    Accuracy:  {metrics['accuracy']:.3f}")

    # Get rankings
    rankings_list = engine.get_rankings(elo)
    rankings = pd.DataFrame(rankings_list, columns=['team', 'rating'])

    # Save rankings (top 10 + bottom 5)
    n_teams = len(rankings)
    top_10 = rankings.head(10)
    bottom_5 = rankings.tail(5)

    rankings_output = pd.concat([top_10, bottom_5])
    rankings_path = output_dir / 'rankings.csv'
    rankings_output.to_csv(rankings_path, index=False)
    print(f"\n  Top 10 Teams:")
    for idx, row in top_10.iterrows():
        print(f"    {idx+1:2d}. {row['team']:25s}  {row['rating']:.0f}")

    # Plot trajectories
    plot_elo_trajectories(df_with_preds, league_name, output_dir)

    # Return summary metrics
    return {
        'league': league_name,
        'league_id': league_id,
        'matches': len(df),
        'teams': len(set(df['HomeTeam']) | set(df['AwayTeam'])),
        'seasons': df['Season'].nunique(),
        'log_loss': metrics['log_loss'],
        'brier': metrics['brier'],
        'accuracy': metrics['accuracy'],
        'top_team': rankings.iloc[0]['team'],
        'top_rating': rankings.iloc[0]['rating']
    }


def main():
    """Main execution function."""
    print("Multi-League Elo Analysis")
    print("=" * 60)

    # Load settings
    settings = EloSettings()
    print(f"\nElo Parameters:")
    print(f"  K-factor:           {settings.k_factor}")
    print(f"  Home Advantage:     {settings.home_advantage}")
    print(f"  Decay Rate:         {settings.decay_rate}")
    print(f"  Promoted Team Elo:  {settings.promoted_elo}")
    print(f"  Logistic Spread:    {settings.spread}")

    # Create output directory
    output_base = Path(__file__).parent / 'outputs' / 'multi_league'
    output_base.mkdir(parents=True, exist_ok=True)

    # Load all leagues
    print("\nLoading league data...")
    all_leagues = load_all_leagues()

    # Analyze each league
    results = []
    for league_id in ['epl', 'laliga', 'bundesliga', 'seriea', 'ligue1']:
        if league_id not in all_leagues:
            print(f"Warning: No data for {league_id}")
            continue

        league_output = output_base / league_id
        result = analyze_league(
            league_id=league_id,
            df=all_leagues[league_id],
            settings=settings,
            output_dir=league_output
        )
        results.append(result)

    # Create cross-league comparison table
    print(f"\n{'='*60}")
    print("CROSS-LEAGUE COMPARISON")
    print(f"{'='*60}\n")

    comparison_df = pd.DataFrame(results)
    comparison_df = comparison_df.sort_values('log_loss')

    # Display table
    print(f"{'League':<20} {'Matches':>8} {'Teams':>6} {'Log Loss':>10} {'Brier':>8} {'Accuracy':>9} {'Top Team':<20} {'Rating':>7}")
    print("-" * 110)
    for _, row in comparison_df.iterrows():
        print(f"{row['league']:<20} {row['matches']:>8} {row['teams']:>6} "
              f"{row['log_loss']:>10.4f} {row['brier']:>8.4f} {row['accuracy']:>9.3f} "
              f"{row['top_team']:<20} {row['top_rating']:>7.0f}")

    # Save comparison table
    comparison_path = output_base / 'cross_league_comparison.csv'
    comparison_df.to_csv(comparison_path, index=False)
    print(f"\nCross-league comparison saved to: {comparison_path}")

    # Summary statistics
    print(f"\n{'='*60}")
    print("SUMMARY STATISTICS")
    print(f"{'='*60}")
    print(f"  Mean Log Loss:  {comparison_df['log_loss'].mean():.4f}")
    print(f"  Mean Brier:     {comparison_df['brier'].mean():.4f}")
    print(f"  Mean Accuracy:  {comparison_df['accuracy'].mean():.3f}")
    print(f"\n  Best League (Log Loss): {comparison_df.iloc[0]['league']}")
    print(f"  Worst League (Log Loss): {comparison_df.iloc[-1]['league']}")

    print(f"\n{'='*60}")
    print(f"Analysis complete. All outputs saved to:")
    print(f"  {output_base}")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
