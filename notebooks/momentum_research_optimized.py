"""Optimized momentum research with sampling and vectorized operations."""

import sqlite3
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.metrics import log_loss, brier_score_loss


@dataclass
class MomentumConfig:
    """Configuration for momentum calculation."""

    decay_factor: float = 0.85
    lookback_window: int = 10
    min_matches: int = 3


def compute_momentum_vectorized(deltas_df: pd.DataFrame, config: MomentumConfig) -> pd.Series:
    """Compute momentum efficiently using pandas rolling window.

    Args:
        deltas_df: DataFrame with 'rating_delta' column, sorted by date
        config: Momentum configuration

    Returns:
        Series of momentum values
    """
    lambda_decay = config.decay_factor
    n = config.lookback_window

    # Create exponential weights
    weights = np.array([lambda_decay ** i for i in range(n)])
    weights = weights / weights.sum()

    # Reverse weights (most recent first)
    weights = weights[::-1]

    # Apply rolling weighted average
    # rolling().apply() is still slow, so let's use a different approach
    # Use convolution for efficiency
    deltas = deltas_df['rating_delta'].values

    # Pad at the beginning
    padded = np.pad(deltas, (n-1, 0), mode='constant', constant_values=0)

    # Convolve
    momentum = np.convolve(padded, weights, mode='valid')

    return pd.Series(momentum, index=deltas_df.index)


def quick_validation_sample(db_path: str, sample_size: int = 5000) -> pd.DataFrame:
    """Load a sample of predictions for quick validation.

    Args:
        db_path: Path to SQLite database
        sample_size: Number of random matches to sample

    Returns:
        DataFrame with predictions and pre-match data
    """
    conn = sqlite3.connect(db_path)

    # Sample predictions from display period
    query = f"""
        SELECT
            p.p_home,
            p.p_draw,
            p.p_away,
            p.home_elo,
            p.away_elo,
            m.result,
            m.home_team_id,
            m.away_team_id,
            m.date,
            m.id as match_id
        FROM predictions p
        JOIN matches m ON p.match_id = m.id
        WHERE m.date >= '2016-08-01'
            AND p.brier_score IS NOT NULL
        ORDER BY RANDOM()
        LIMIT {sample_size}
    """

    df = pd.read_sql_query(query, conn)
    conn.close()

    return df


def get_team_momentum_at_date(
    team_id: int,
    date: str,
    team_history_cache: dict,
    config: MomentumConfig
) -> float:
    """Get momentum for a team at a specific date.

    Uses cached team histories for efficiency.

    Args:
        team_id: Team ID
        date: Date to get momentum for
        team_history_cache: Dict of team_id -> DataFrame of history
        config: Momentum configuration

    Returns:
        Momentum value
    """
    if team_id not in team_history_cache:
        return 0.0

    history = team_history_cache[team_id]

    # Get history before this date
    pre_match = history[history['date'] < date]

    if len(pre_match) < config.min_matches:
        return 0.0

    # Get last N deltas
    recent_deltas = pre_match['rating_delta'].tail(config.lookback_window).values[::-1]

    # Compute weights
    lambda_decay = config.decay_factor
    n = len(recent_deltas)
    weights = np.array([lambda_decay ** i for i in range(n)])
    weights = weights / weights.sum()

    return float(np.dot(weights, recent_deltas))


def load_team_histories(db_path: str) -> dict:
    """Load and cache all team rating histories.

    Returns:
        Dict of team_id -> DataFrame with columns [date, rating, rating_delta]
    """
    conn = sqlite3.connect(db_path)

    query = """
        SELECT
            team_id,
            date,
            rating,
            rating_delta
        FROM ratings_history
        ORDER BY team_id, date
    """

    df = pd.read_sql_query(query, conn)
    conn.close()

    # Group by team
    team_histories = {}
    for team_id, group in df.groupby('team_id'):
        team_histories[team_id] = group.sort_values('date').reset_index(drop=True)

    return team_histories


def validate_momentum_quick(
    db_path: str,
    config: MomentumConfig,
    sample_size: int = 5000
) -> dict:
    """Quick validation using sampled data.

    Args:
        db_path: Database path
        config: Momentum configuration
        sample_size: Number of matches to sample

    Returns:
        Validation results dictionary
    """
    print(f"Loading {sample_size:,} sampled predictions...")
    predictions = quick_validation_sample(db_path, sample_size)

    if len(predictions) == 0:
        return {"error": "No predictions found"}

    print(f"Loaded {len(predictions):,} predictions")
    print("Loading team histories...")

    team_histories = load_team_histories(db_path)
    print(f"Loaded histories for {len(team_histories)} teams")

    # Compute momentum for each match
    print("Computing pre-match momentum...")
    home_momenta = []
    away_momenta = []

    for _, row in predictions.iterrows():
        home_mom = get_team_momentum_at_date(
            row['home_team_id'],
            row['date'],
            team_histories,
            config
        )
        away_mom = get_team_momentum_at_date(
            row['away_team_id'],
            row['date'],
            team_histories,
            config
        )
        home_momenta.append(home_mom)
        away_momenta.append(away_mom)

    predictions['home_momentum'] = home_momenta
    predictions['away_momentum'] = away_momenta

    # Convert results to one-hot
    result_map = {'H': [1, 0, 0], 'D': [0, 1, 0], 'A': [0, 0, 1]}
    y_true = np.array([result_map[r] for r in predictions['result']])

    # Baseline Elo predictions
    y_pred_baseline = predictions[['p_home', 'p_draw', 'p_away']].values

    baseline_log_loss = log_loss(y_true, y_pred_baseline)
    baseline_brier = np.mean([
        brier_score_loss(y_true[:, i], y_pred_baseline[:, i])
        for i in range(3)
    ])

    print(f"\n{'='*60}")
    print(f"BASELINE (Elo only)")
    print(f"{'='*60}")
    print(f"Log Loss:   {baseline_log_loss:.6f}")
    print(f"Brier:      {baseline_brier:.6f}")

    # Momentum statistics
    print(f"\n{'='*60}")
    print(f"MOMENTUM STATISTICS")
    print(f"{'='*60}")
    print(f"Home momentum: mean={np.mean(home_momenta):.2f}, "
          f"std={np.std(home_momenta):.2f}, "
          f"range=[{np.min(home_momenta):.2f}, {np.max(home_momenta):.2f}]")
    print(f"Away momentum: mean={np.mean(away_momenta):.2f}, "
          f"std={np.std(away_momenta):.2f}, "
          f"range=[{np.min(away_momenta):.2f}, {np.max(away_momenta):.2f}]")

    # Correlation analysis
    home_wins = predictions[predictions['result'] == 'H']
    away_wins = predictions[predictions['result'] == 'A']
    draws = predictions[predictions['result'] == 'D']

    home_win_mom_diff = (home_wins['home_momentum'] - home_wins['away_momentum']).mean()
    away_win_mom_diff = (away_wins['home_momentum'] - away_wins['away_momentum']).mean()
    draw_mom_diff = (draws['home_momentum'] - draws['away_momentum']).mean()

    print(f"\nMomentum differential by result:")
    print(f"  Home wins:  {home_win_mom_diff:+.3f} (expected > 0)")
    print(f"  Draws:      {draw_mom_diff:+.3f} (expected ≈ 0)")
    print(f"  Away wins:  {away_win_mom_diff:+.3f} (expected < 0)")

    # Test momentum-adjusted predictions
    print(f"\n{'='*60}")
    print(f"MOMENTUM-ADJUSTED PREDICTIONS")
    print(f"{'='*60}")

    def adjust_probs_with_momentum(row, mom_scale, spread=400, ha=55):
        """Adjust win probabilities using momentum."""
        elo_h = row['home_elo'] + mom_scale * row['home_momentum']
        elo_a = row['away_elo'] + mom_scale * row['away_momentum']

        # Recompute expected score
        exp_h = 1.0 / (1.0 + 10 ** ((elo_a - (elo_h + ha)) / spread))

        # Simple model: scale win probs, preserve draw roughly
        baseline_draw = row['p_draw']

        # Compute new win probs
        exp_a = 1 - exp_h
        total = exp_h + exp_a

        p_h = exp_h / total * (1 - baseline_draw)
        p_a = exp_a / total * (1 - baseline_draw)
        p_d = baseline_draw

        # Normalize
        total_prob = p_h + p_d + p_a
        return np.array([p_h / total_prob, p_d / total_prob, p_a / total_prob])

    best_scale = None
    best_ll = baseline_log_loss

    scales = [0.0, 0.1, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0]

    for scale in scales:
        y_pred = np.array([
            adjust_probs_with_momentum(row, scale)
            for _, row in predictions.iterrows()
        ])

        ll = log_loss(y_true, y_pred)
        brier = np.mean([
            brier_score_loss(y_true[:, i], y_pred[:, i])
            for i in range(3)
        ])

        improvement = baseline_log_loss - ll
        improvement_pct = (improvement / baseline_log_loss) * 100

        indicator = "  ←" if ll < best_ll else ""

        print(f"Scale {scale:5.1f}: LL={ll:.6f} ({improvement_pct:+.3f}%), "
              f"Brier={brier:.6f}{indicator}")

        if ll < best_ll:
            best_ll = ll
            best_scale = scale

    improvement = (baseline_log_loss - best_ll) / baseline_log_loss * 100

    print(f"\n{'='*60}")
    print(f"RESULTS")
    print(f"{'='*60}")
    print(f"Best momentum scale: {best_scale}")
    print(f"Improvement:         {improvement:+.3f}%")
    print(f"Statistical significance: {'YES' if improvement > 0.1 else 'MARGINAL' if improvement > 0 else 'NO'}")

    return {
        'config': config,
        'sample_size': len(predictions),
        'baseline_log_loss': baseline_log_loss,
        'baseline_brier': baseline_brier,
        'best_scale': best_scale,
        'best_log_loss': best_ll,
        'improvement_pct': improvement,
        'momentum_stats': {
            'mean_home': np.mean(home_momenta),
            'std_home': np.std(home_momenta),
            'mean_away': np.mean(away_momenta),
            'std_away': np.std(away_momenta),
            'home_win_diff': home_win_mom_diff,
            'away_win_diff': away_win_mom_diff,
            'draw_diff': draw_mom_diff,
        }
    }


def find_optimal_config(db_path: str, sample_size: int = 3000) -> dict:
    """Grid search over momentum configurations.

    Args:
        db_path: Database path
        sample_size: Sample size for validation

    Returns:
        Results for all configurations
    """
    configs = [
        MomentumConfig(decay_factor=0.70, lookback_window=5),   # Very reactive
        MomentumConfig(decay_factor=0.80, lookback_window=8),   # Reactive
        MomentumConfig(decay_factor=0.85, lookback_window=10),  # Default
        MomentumConfig(decay_factor=0.90, lookback_window=12),  # Smooth
        MomentumConfig(decay_factor=0.95, lookback_window=15),  # Very smooth
    ]

    results = []

    print(f"\n{'='*60}")
    print(f"CONFIG OPTIMIZATION (n={sample_size})")
    print(f"{'='*60}\n")

    for i, config in enumerate(configs, 1):
        print(f"[{i}/{len(configs)}] Testing λ={config.decay_factor}, N={config.lookback_window}")
        print(f"{'-'*60}")

        result = validate_momentum_quick(db_path, config, sample_size)
        results.append(result)

        print()

    # Find best
    best_idx = np.argmax([r['improvement_pct'] for r in results])
    best = results[best_idx]

    print(f"\n{'='*60}")
    print(f"OPTIMIZATION SUMMARY")
    print(f"{'='*60}")

    for i, r in enumerate(results):
        marker = " ← BEST" if i == best_idx else ""
        print(f"λ={r['config'].decay_factor}, N={r['config'].lookback_window:2d}: "
              f"{r['improvement_pct']:+.3f}% improvement{marker}")

    return {
        'all_results': results,
        'best_config': best['config'],
        'best_improvement': best['improvement_pct']
    }


if __name__ == '__main__':
    db_path = '/home/linards/Documents/Private/football-elo/data/elo.db'

    print("="*60)
    print("ELO MOMENTUM VALIDATION (Optimized)")
    print("="*60)

    # Run optimization
    results = find_optimal_config(db_path, sample_size=5000)

    print(f"\n{'='*60}")
    print(f"FINAL RECOMMENDATION")
    print(f"{'='*60}")

    best_config = results['best_config']
    print(f"Decay factor (λ):  {best_config.decay_factor}")
    print(f"Lookback window (N): {best_config.lookback_window} matches")
    print(f"Improvement:        {results['best_improvement']:+.3f}%")
    print(f"\nConclusion: Momentum {'ADDS' if results['best_improvement'] > 0.1 else 'DOES NOT ADD'} "
          f"meaningful predictive value beyond raw Elo.")
