"""Match prediction using current Elo ratings.

Extracts prediction logic from notebooks/run_unified.py into a reusable module.
"""

from src.config import EloSettings
from src.elo_engine import EloEngine


def predict_probs(e_home: float) -> tuple[float, float, float]:
    """Convert home expected score to (p_home, p_draw, p_away) probabilities.

    Uses a draw probability model that accounts for the rating gap:
    closer ratings → higher draw probability.

    Args:
        e_home: Home team's expected score from the Elo model (0.0 to 1.0).

    Returns:
        Tuple of (p_home, p_draw, p_away) summing to 1.0.
    """
    e_away = 1.0 - e_home
    rating_gap = abs(e_home - e_away)
    p_draw = max(0.05, 0.34 * (1.0 - rating_gap))
    remaining = 1.0 - p_draw
    return remaining * e_home, p_draw, remaining * e_away


def predict_match(
    home_team: str,
    away_team: str,
    ratings: dict[str, float],
    settings: EloSettings | None = None,
) -> dict:
    """Predict match outcome probabilities from current ratings.

    Args:
        home_team: Home team name (canonical form).
        away_team: Away team name (canonical form).
        ratings: Dict mapping team name to current Elo rating.
        settings: Elo settings (for home advantage, spread). Uses defaults if None.

    Returns:
        Dict with keys:
            home_team, away_team,
            home_rating, away_rating,
            p_home, p_draw, p_away,
            rating_diff (home - away).

    Raises:
        KeyError: If either team is not found in ratings.
    """
    if home_team not in ratings:
        raise KeyError(f"Team not found in ratings: {home_team}")
    if away_team not in ratings:
        raise KeyError(f"Team not found in ratings: {away_team}")

    settings = settings or EloSettings()
    engine = EloEngine(settings)

    home_rating = ratings[home_team]
    away_rating = ratings[away_team]

    e_home = engine.expected_score(
        home_rating + settings.home_advantage, away_rating
    )
    p_home, p_draw, p_away = predict_probs(e_home)

    return {
        "home_team": home_team,
        "away_team": away_team,
        "home_rating": round(home_rating, 1),
        "away_rating": round(away_rating, 1),
        "p_home": round(p_home, 4),
        "p_draw": round(p_draw, 4),
        "p_away": round(p_away, 4),
        "rating_diff": round(home_rating - away_rating, 1),
    }


def predict_match_from_db(
    home_team: str,
    away_team: str,
    db_path: str | None = None,
    settings: EloSettings | None = None,
) -> dict:
    """Predict match outcome using latest ratings from the database.

    Convenience wrapper that loads ratings from DB.

    Args:
        home_team: Home team name.
        away_team: Away team name.
        db_path: Path to SQLite database.
        settings: Elo settings.

    Returns:
        Prediction dict (same as predict_match).
    """
    from src.db.connection import get_connection
    from src.db.repository import get_ratings_at_date, get_latest_match_date

    conn = get_connection(db_path)
    latest_date = get_latest_match_date(conn)
    if latest_date is None:
        conn.close()
        raise ValueError("No matches in database")

    ratings = get_ratings_at_date(conn, latest_date)
    conn.close()

    return predict_match(home_team, away_team, ratings, settings)
