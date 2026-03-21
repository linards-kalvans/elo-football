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
    db_path: str | Path | None = None,
    competition: str | None = None,
    source: str | None = None,
    country: str | None = None,
    team_id: int | None = None,
) -> dict:
    """Get aggregate prediction accuracy statistics.

    Args:
        db_path: Path to SQLite database. Defaults to data/elo.db.
        competition: Optional competition name to filter by.
        source: Optional source filter ('live', 'backfill', or None for all).
        country: Optional country name to filter by.
        team_id: Optional team ID to filter by.

    Returns:
        Dict with total_predictions, mean_brier_score, median_brier_score,
        calibration buckets, by_competition breakdown, recent_form, and
        by_source breakdown.
    """
    path = str(db_path) if db_path else str(get_db_path())
    conn = await aiosqlite.connect(path)
    conn.row_factory = aiosqlite.Row

    try:
        # Build WHERE clauses
        where_parts = ["p.brier_score IS NOT NULL"]
        params: list = []

        if competition:
            where_parts.append("COALESCE(c1.name, c2.name) = ?")
            params.append(competition)
        elif country:
            where_parts.append("COALESCE(c1.country, c2.country) = ?")
            params.append(country)

        if team_id is not None:
            where_parts.append(
                """(COALESCE(m.home_team_id, f.home_team_id) = ?
                   OR COALESCE(m.away_team_id, f.away_team_id) = ?)"""
            )
            params.extend([team_id, team_id])

        if source:
            where_parts.append("p.source = ?")
            params.append(source)

        where_sql = " AND ".join(where_parts)

        cursor = await conn.execute(
            f"""SELECT p.id, p.p_home, p.p_draw, p.p_away, p.brier_score,
                       p.source, p.scored_at,
                       COALESCE(m.result, m2.result) as result,
                       COALESCE(c1.name, c2.name) as comp_name,
                       COALESCE(m.date, f.date) as match_date
                FROM predictions p
                LEFT JOIN matches m ON m.id = p.match_id
                LEFT JOIN competitions c1 ON c1.id = m.competition_id
                LEFT JOIN fixtures f ON f.id = p.fixture_id
                LEFT JOIN matches m2 ON m2.date = f.date
                    AND m2.home_team_id = f.home_team_id
                    AND m2.away_team_id = f.away_team_id
                LEFT JOIN competitions c2 ON c2.id = f.competition_id
                WHERE {where_sql}
                ORDER BY COALESCE(m.date, f.date) ASC, p.id ASC""",
            params,
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

        # Time series: rolling Brier score (window=50)
        time_series = _compute_brier_time_series(rows, window=50)

        # By source breakdown
        by_source: dict[str, list[float]] = {}
        for row in rows:
            src = row["source"] or "live"
            if src not in by_source:
                by_source[src] = []
            by_source[src].append(row["brier_score"])

        by_source_stats = {
            src: {
                "count": len(scores),
                "mean_brier_score": round(statistics.mean(scores), 4),
            }
            for src, scores in by_source.items()
        }

        return {
            "total_predictions": total,
            "mean_brier_score": round(mean_brier, 4),
            "median_brier_score": round(median_brier, 4),
            "calibration": buckets,
            "by_competition": by_competition_stats,
            "by_source": by_source_stats,
            "recent_form": recent_form,
            "time_series": time_series,
        }
    finally:
        await conn.close()


def _compute_brier_time_series(
    rows: list, window: int = 50
) -> list[dict]:
    """Compute rolling Brier score time series from scored prediction rows.

    Groups predictions by match date, then computes a rolling average
    over the specified window of predictions.

    Args:
        rows: List of Row objects with brier_score and match_date fields.
            Rows must be ordered by match_date ASC, id ASC.
        window: Number of predictions in the rolling window.

    Returns:
        List of dicts with date, rolling_brier, and count fields.
    """
    if len(rows) < window:
        return []

    # Rows are ordered by match_date ASC from the query
    time_series = []
    scores = [row["brier_score"] for row in rows]

    # Track the last date we emitted to avoid duplicates
    last_emitted_date = None

    for i in range(window - 1, len(scores)):
        window_scores = scores[i - window + 1 : i + 1]
        rolling_avg = statistics.mean(window_scores)

        # Use match_date for the time axis (not scored_at)
        match_date = rows[i]["match_date"]
        if not match_date or len(str(match_date)) < 10:
            continue
        point_date = str(match_date)[:10]

        # Only emit one point per date (the last rolling value for that date)
        if point_date != last_emitted_date:
            time_series.append({
                "date": point_date,
                "rolling_brier": round(rolling_avg, 4),
                "count": len(window_scores),
            })
            last_emitted_date = point_date
        else:
            # Update the last entry for this date
            time_series[-1] = {
                "date": point_date,
                "rolling_brier": round(rolling_avg, 4),
                "count": len(window_scores),
            }

    return time_series


async def get_prediction_history(
    db_path: str | Path | None = None,
    page: int = 1,
    per_page: int = 20,
    competition: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    source: str | None = None,
    country: str | None = None,
    team_id: int | None = None,
    search: str | None = None,
) -> dict:
    """Get paginated list of scored predictions with match details.

    Args:
        db_path: Path to SQLite database. Defaults to data/elo.db.
        page: Page number (1-indexed).
        per_page: Number of items per page (max 100).
        competition: Optional competition name filter.
        date_from: Optional start date filter (YYYY-MM-DD).
        date_to: Optional end date filter (YYYY-MM-DD).
        source: Optional source filter ('live', 'backfill', or None for all).
        country: Optional country name to filter by.
        team_id: Optional team ID to filter by.
        search: Optional team name search string. Whitespace-separated tokens;
            all tokens must match at least one team name (AND logic).

    Returns:
        Dict with items, total, page, per_page, and pages.
    """
    path = str(db_path) if db_path else str(get_db_path())
    conn = await aiosqlite.connect(path)
    conn.row_factory = aiosqlite.Row

    try:
        # Build WHERE clauses and params
        where_clauses = ["p.brier_score IS NOT NULL"]
        params: list = []

        if competition:
            where_clauses.append("COALESCE(c1.name, c2.name) = ?")
            params.append(competition)
        elif country:
            where_clauses.append("COALESCE(c1.country, c2.country) = ?")
            params.append(country)

        if team_id is not None:
            where_clauses.append(
                """(COALESCE(m.home_team_id, f.home_team_id) = ?
                   OR COALESCE(m.away_team_id, f.away_team_id) = ?)"""
            )
            params.extend([team_id, team_id])

        if date_from:
            where_clauses.append("COALESCE(m.date, f.date) >= ?")
            params.append(date_from)

        if date_to:
            where_clauses.append("COALESCE(m.date, f.date) <= ?")
            params.append(date_to)

        if source:
            where_clauses.append("p.source = ?")
            params.append(source)

        if search:
            tokens = search.strip().split()
            for token in tokens:
                where_clauses.append(
                    "(LOWER(COALESCE(th1.name, th2.name)) LIKE ?"
                    " OR LOWER(COALESCE(ta1.name, ta2.name)) LIKE ?)"
                )
                like_val = f"%{token.lower()}%"
                params.extend([like_val, like_val])

        where_sql = " AND ".join(where_clauses)

        base_from = """
            FROM predictions p
            LEFT JOIN matches m ON m.id = p.match_id
            LEFT JOIN competitions c1 ON c1.id = m.competition_id
            LEFT JOIN teams th1 ON th1.id = m.home_team_id
            LEFT JOIN teams ta1 ON ta1.id = m.away_team_id
            LEFT JOIN fixtures f ON f.id = p.fixture_id
            LEFT JOIN competitions c2 ON c2.id = f.competition_id
            LEFT JOIN teams th2 ON th2.id = f.home_team_id
            LEFT JOIN teams ta2 ON ta2.id = f.away_team_id
            LEFT JOIN matches m2 ON m2.date = f.date
                AND m2.home_team_id = f.home_team_id
                AND m2.away_team_id = f.away_team_id
        """

        # Count total
        count_sql = f"SELECT COUNT(*) as cnt {base_from} WHERE {where_sql}"
        cursor = await conn.execute(count_sql, params)
        count_row = await cursor.fetchone()
        total = count_row["cnt"] if count_row else 0

        # Calculate pagination
        per_page = min(per_page, 100)
        pages = max(1, (total + per_page - 1) // per_page)
        offset = (page - 1) * per_page

        # Fetch items
        items_sql = f"""
            SELECT
                COALESCE(m.date, f.date) as match_date,
                COALESCE(th1.name, th2.name) as home_team,
                COALESCE(ta1.name, ta2.name) as away_team,
                COALESCE(c1.name, c2.name) as competition,
                p.p_home, p.p_draw, p.p_away,
                COALESCE(m.result, m2.result) as actual_result,
                COALESCE(m.home_goals, m2.home_goals) as home_goals,
                COALESCE(m.away_goals, m2.away_goals) as away_goals,
                p.brier_score,
                p.home_elo,
                p.away_elo,
                p.source
            {base_from}
            WHERE {where_sql}
            ORDER BY COALESCE(m.date, f.date) DESC, p.id DESC
            LIMIT ? OFFSET ?
        """
        cursor = await conn.execute(items_sql, params + [per_page, offset])
        rows = await cursor.fetchall()

        items = [
            {
                "date": row["match_date"],
                "home_team": row["home_team"],
                "away_team": row["away_team"],
                "competition": row["competition"] or "Unknown",
                "p_home": round(row["p_home"], 4),
                "p_draw": round(row["p_draw"], 4),
                "p_away": round(row["p_away"], 4),
                "actual_result": row["actual_result"],
                "home_goals": row["home_goals"],
                "away_goals": row["away_goals"],
                "brier_score": round(row["brier_score"], 4),
                "home_elo": round(row["home_elo"], 1),
                "away_elo": round(row["away_elo"], 1),
                "source": row["source"] or "live",
            }
            for row in rows
        ]

        return {
            "items": items,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": pages,
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
