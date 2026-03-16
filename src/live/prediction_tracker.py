"""Prediction accuracy tracking with Brier scores.

Scores completed predictions against actual match results and provides
aggregate accuracy statistics including calibration analysis.
"""

import logging
import statistics
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from src.db.connection import get_async_connection, get_db_path
from src.prediction import predict_match

logger = logging.getLogger(__name__)


def compute_brier_score(
    p_home: float, p_draw: float, p_away: float, result: str
) -> float:
    """Compute Brier score for a single prediction.

    Brier score formula:
        BS = (p_home - actual_home)^2 + (p_draw - actual_draw)^2 + (p_away - actual_away)^2

    Lower is better: 0 = perfect prediction, 2 = worst possible.

    Args:
        p_home: Predicted home win probability.
        p_draw: Predicted draw probability.
        p_away: Predicted away win probability.
        result: Actual match result ('H', 'D', or 'A').

    Returns:
        Brier score as a float.
    """
    actual_home = 1.0 if result == "H" else 0.0
    actual_draw = 1.0 if result == "D" else 0.0
    actual_away = 1.0 if result == "A" else 0.0

    return (
        (p_home - actual_home) ** 2
        + (p_draw - actual_draw) ** 2
        + (p_away - actual_away) ** 2
    )


async def score_completed_matches(db_path: str | Path | None = None) -> dict:
    """Score predictions for completed matches that haven't been scored yet.

    Finds predictions linked to matches (via match_id) that have no
    brier_score yet, computes the Brier score from the actual result,
    and stores it.

    Args:
        db_path: Path to SQLite database. Defaults to data/elo.db.

    Returns:
        Dict with scored_count and errors.
    """
    path = str(db_path) if db_path else str(get_db_path())
    conn = await aiosqlite.connect(path)
    conn.row_factory = aiosqlite.Row

    try:
        # Find predictions with a match_id but no brier_score
        cursor = await conn.execute(
            """SELECT p.id, p.p_home, p.p_draw, p.p_away, m.result
               FROM predictions p
               JOIN matches m ON m.id = p.match_id
               WHERE p.match_id IS NOT NULL
                 AND p.brier_score IS NULL"""
        )
        rows = await cursor.fetchall()

        scored_count = 0
        errors = 0
        now = datetime.now(timezone.utc).isoformat()

        for row in rows:
            try:
                brier = compute_brier_score(
                    row["p_home"], row["p_draw"], row["p_away"], row["result"]
                )
                await conn.execute(
                    "UPDATE predictions SET brier_score = ?, scored_at = ? WHERE id = ?",
                    (brier, now, row["id"]),
                )
                scored_count += 1
            except Exception:
                logger.warning("Failed to score prediction %d", row["id"])
                errors += 1

        # Also score predictions linked via fixture_id where the fixture
        # has been completed and linked to a match
        cursor = await conn.execute(
            """SELECT p.id, p.p_home, p.p_draw, p.p_away, m.result
               FROM predictions p
               JOIN fixtures f ON f.id = p.fixture_id
               JOIN matches m ON m.date = f.date
                   AND m.home_team_id = f.home_team_id
                   AND m.away_team_id = f.away_team_id
               WHERE p.fixture_id IS NOT NULL
                 AND p.brier_score IS NULL
                 AND f.status = 'completed'"""
        )
        fixture_rows = await cursor.fetchall()

        for row in fixture_rows:
            try:
                brier = compute_brier_score(
                    row["p_home"], row["p_draw"], row["p_away"], row["result"]
                )
                await conn.execute(
                    "UPDATE predictions SET brier_score = ?, scored_at = ? WHERE id = ?",
                    (brier, now, row["id"]),
                )
                scored_count += 1
            except Exception:
                logger.warning("Failed to score fixture prediction %d", row["id"])
                errors += 1

        await conn.commit()
        return {"scored_count": scored_count, "errors": errors}
    finally:
        await conn.close()


async def get_prediction_accuracy(
    db_path: str | Path | None = None, competition: str | None = None
) -> dict:
    """Get aggregate prediction accuracy statistics.

    Args:
        db_path: Path to SQLite database. Defaults to data/elo.db.
        competition: Optional competition name to filter by.

    Returns:
        Dict with total_predictions, mean_brier_score, median_brier_score,
        calibration buckets, by_competition breakdown, and recent_form.
    """
    path = str(db_path) if db_path else str(get_db_path())
    conn = await aiosqlite.connect(path)
    conn.row_factory = aiosqlite.Row

    try:
        # Build base query for scored predictions
        if competition:
            # Join through match->competition or fixture->competition
            cursor = await conn.execute(
                """SELECT p.id, p.p_home, p.p_draw, p.p_away, p.brier_score,
                          COALESCE(m.result, m2.result) as result,
                          COALESCE(c1.name, c2.name) as comp_name
                   FROM predictions p
                   LEFT JOIN matches m ON m.id = p.match_id
                   LEFT JOIN competitions c1 ON c1.id = m.competition_id
                   LEFT JOIN fixtures f ON f.id = p.fixture_id
                   LEFT JOIN matches m2 ON m2.date = f.date
                       AND m2.home_team_id = f.home_team_id
                       AND m2.away_team_id = f.away_team_id
                   LEFT JOIN competitions c2 ON c2.id = f.competition_id
                   WHERE p.brier_score IS NOT NULL
                     AND COALESCE(c1.name, c2.name) = ?
                   ORDER BY p.scored_at ASC""",
                (competition,),
            )
        else:
            cursor = await conn.execute(
                """SELECT p.id, p.p_home, p.p_draw, p.p_away, p.brier_score,
                          COALESCE(m.result, m2.result) as result,
                          COALESCE(c1.name, c2.name) as comp_name
                   FROM predictions p
                   LEFT JOIN matches m ON m.id = p.match_id
                   LEFT JOIN competitions c1 ON c1.id = m.competition_id
                   LEFT JOIN fixtures f ON f.id = p.fixture_id
                   LEFT JOIN matches m2 ON m2.date = f.date
                       AND m2.home_team_id = f.home_team_id
                       AND m2.away_team_id = f.away_team_id
                   LEFT JOIN competitions c2 ON c2.id = f.competition_id
                   WHERE p.brier_score IS NOT NULL
                   ORDER BY p.scored_at ASC"""
            )

        rows = await cursor.fetchall()

        if not rows:
            return {
                "total_predictions": 0,
                "mean_brier_score": None,
                "median_brier_score": None,
                "calibration": {},
                "by_competition": {},
                "recent_form": None,
            }

        brier_scores = [row["brier_score"] for row in rows]
        total = len(brier_scores)
        mean_brier = statistics.mean(brier_scores)
        median_brier = statistics.median(brier_scores)

        # Calibration: for each probability bucket, what % actually occurred
        # We check each outcome (home/draw/away) independently
        # Use integer arithmetic to avoid floating point boundary issues
        buckets = {}
        for i in range(10):
            low = i / 10
            high = (i + 1) / 10
            bucket_key = f"{i * 10}-{(i + 1) * 10}%"
            predicted_in_bucket = []

            for row in rows:
                result = row["result"]
                # Check each probability against its actual outcome
                for prob, outcome in [
                    (row["p_home"], "H"),
                    (row["p_draw"], "D"),
                    (row["p_away"], "A"),
                ]:
                    if low <= prob < high or (i == 9 and prob == 1.0):
                        actual = 1.0 if result == outcome else 0.0
                        predicted_in_bucket.append(actual)

            if predicted_in_bucket:
                buckets[bucket_key] = {
                    "count": len(predicted_in_bucket),
                    "actual_frequency": round(
                        statistics.mean(predicted_in_bucket), 4
                    ),
                    "expected_midpoint": round((low + high) / 2, 2),
                }
            else:
                buckets[bucket_key] = {
                    "count": 0,
                    "actual_frequency": None,
                    "expected_midpoint": round((low + high) / 2, 2),
                }

        # By competition breakdown
        by_competition = {}
        for row in rows:
            comp = row["comp_name"] or "Unknown"
            if comp not in by_competition:
                by_competition[comp] = []
            by_competition[comp].append(row["brier_score"])

        by_competition_stats = {
            comp: {
                "count": len(scores),
                "mean_brier_score": round(statistics.mean(scores), 4),
            }
            for comp, scores in by_competition.items()
        }

        # Recent form: last 100 predictions
        recent_scores = brier_scores[-100:]
        recent_form = round(statistics.mean(recent_scores), 4)

        return {
            "total_predictions": total,
            "mean_brier_score": round(mean_brier, 4),
            "median_brier_score": round(median_brier, 4),
            "calibration": buckets,
            "by_competition": by_competition_stats,
            "recent_form": recent_form,
        }
    finally:
        await conn.close()


async def generate_fixture_predictions(
    db_path: str | Path | None = None,
) -> int:
    """Generate predictions for fixtures that don't have one yet.

    Uses current Elo ratings to predict match outcomes for all scheduled
    fixtures without existing predictions.

    Args:
        db_path: Path to SQLite database. Defaults to data/elo.db.

    Returns:
        Count of new predictions generated.
    """
    path = str(db_path) if db_path else str(get_db_path())
    conn = await aiosqlite.connect(path)
    conn.row_factory = aiosqlite.Row

    try:
        # Get fixtures without predictions
        cursor = await conn.execute(
            """SELECT f.id, f.home_team_id, f.away_team_id,
                      th.name as home_team, ta.name as away_team
               FROM fixtures f
               JOIN teams th ON th.id = f.home_team_id
               JOIN teams ta ON ta.id = f.away_team_id
               WHERE f.status = 'scheduled'
                 AND f.id NOT IN (
                     SELECT fixture_id FROM predictions WHERE fixture_id IS NOT NULL
                 )"""
        )
        fixtures = await cursor.fetchall()

        if not fixtures:
            return 0

        # Get latest ratings
        cursor = await conn.execute("SELECT MAX(date) as max_date FROM matches")
        date_row = await cursor.fetchone()
        latest_date = date_row["max_date"] if date_row else None

        if latest_date is None:
            return 0

        cursor = await conn.execute(
            """SELECT t.name, rh.rating
               FROM ratings_history rh
               JOIN teams t ON t.id = rh.team_id
               WHERE rh.id IN (
                   SELECT rh2.id FROM ratings_history rh2
                   WHERE rh2.team_id = rh.team_id AND rh2.date <= ?
                   ORDER BY rh2.date DESC, rh2.id DESC
                   LIMIT 1
               )""",
            (latest_date,),
        )
        rating_rows = await cursor.fetchall()
        ratings = {row["name"]: row["rating"] for row in rating_rows}

        count = 0
        for fixture in fixtures:
            home_name = fixture["home_team"]
            away_name = fixture["away_team"]

            if home_name not in ratings or away_name not in ratings:
                logger.warning(
                    "Skipping fixture %d: missing ratings for %s or %s",
                    fixture["id"],
                    home_name,
                    away_name,
                )
                continue

            try:
                pred = predict_match(home_name, away_name, ratings)
                await conn.execute(
                    """INSERT INTO predictions
                       (fixture_id, p_home, p_draw, p_away, home_elo, away_elo)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        fixture["id"],
                        pred["p_home"],
                        pred["p_draw"],
                        pred["p_away"],
                        pred["home_rating"],
                        pred["away_rating"],
                    ),
                )
                count += 1
            except Exception:
                logger.warning(
                    "Failed to predict fixture %d: %s vs %s",
                    fixture["id"],
                    home_name,
                    away_name,
                )

        await conn.commit()
        return count
    finally:
        await conn.close()
