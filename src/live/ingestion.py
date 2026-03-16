"""Live match ingestion from football-data.org.

Fetches recent completed matches and upcoming fixtures from the API,
resolves team names to internal IDs, ingests matches into the database,
recomputes ratings, and generates predictions for fixtures.
"""

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from src.db.connection import get_connection, get_db_path, init_db
from src.db.repository import (
    get_ratings_at_date,
    get_latest_match_date,
    insert_competition,
    insert_fixture,
    insert_prediction,
    insert_team,
)
from src.live.football_data_client import COMPETITION_MAP, FootballDataClient
from src.live.team_mapping import resolve_team
from src.pipeline import run_incremental_update
from src.prediction import predict_match

logger = logging.getLogger(__name__)


# Map football-data.org competition codes to internal competition names
# (matching LEAGUE_CONFIG names in data_loader.py and european_data.py)
_COMPETITION_NAME_MAP = {
    "PL": "Premier League",
    "PD": "La Liga",
    "BL1": "Bundesliga",
    "SA": "Serie A",
    "FL1": "Ligue 1",
    "CL": "Champions League",
    "EL": "Europa League",
    "EC": "Conference League",
}


def _determine_result(home_goals: int, away_goals: int) -> str:
    """Determine match result code from goals.

    Args:
        home_goals: Goals scored by home team.
        away_goals: Goals scored by away team.

    Returns:
        'H' for home win, 'A' for away win, 'D' for draw.
    """
    if home_goals > away_goals:
        return "H"
    elif away_goals > home_goals:
        return "A"
    else:
        return "D"


def _determine_season(date_str: str) -> str:
    """Derive season string from a match date.

    European football seasons span two calendar years (e.g. Aug 2024 - May 2025).
    Returns a 4-character code like '2425'.

    Args:
        date_str: Date in YYYY-MM-DD format.

    Returns:
        Season string (e.g. '2425' for the 2024-25 season).
    """
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    # Season starts in August; if month >= 8, it's the start year
    if dt.month >= 8:
        start_year = dt.year
    else:
        start_year = dt.year - 1
    end_year = start_year + 1
    return f"{start_year % 100:02d}{end_year % 100:02d}"


def _api_match_to_dataframe_row(
    match_data: dict,
    home_name: str,
    away_name: str,
    competition_code: str,
) -> dict:
    """Convert an API match response to a DataFrame-compatible row.

    Args:
        match_data: Single match dict from the API response.
        home_name: Resolved internal home team name.
        away_name: Resolved internal away team name.
        competition_code: Football-data.org competition code (e.g. 'PL').

    Returns:
        Dict with columns matching the DataFrame format expected by
        run_incremental_update.
    """
    utc_date = match_data["utcDate"][:10]  # YYYY-MM-DD
    home_goals = match_data["score"]["fullTime"]["home"]
    away_goals = match_data["score"]["fullTime"]["away"]

    comp_info = COMPETITION_MAP.get(competition_code, {})
    tier = comp_info.get("tier", 5)
    comp_name = _COMPETITION_NAME_MAP.get(competition_code, competition_code)

    return {
        "Date": utc_date,
        "HomeTeam": home_name,
        "AwayTeam": away_name,
        "FTHG": home_goals,
        "FTAG": away_goals,
        "FTR": _determine_result(home_goals, away_goals),
        "Season": _determine_season(utc_date),
        "League": comp_name,
        "Competition": comp_name,
        "Tier": tier,
    }


def _get_known_teams(db_path: str | Path | None = None) -> list[str]:
    """Get all known team names from the database.

    Args:
        db_path: Path to SQLite database.

    Returns:
        List of team name strings.
    """
    conn = get_connection(db_path)
    try:
        rows = conn.execute("SELECT name FROM teams ORDER BY name").fetchall()
        return [row["name"] for row in rows]
    finally:
        conn.close()


async def fetch_and_ingest_matches(
    db_path: str | Path | None = None,
    days_back: int = 14,
    client: FootballDataClient | None = None,
) -> dict:
    """Fetch recent completed matches and ingest into the database.

    Main entry point for ingesting completed matches from football-data.org.
    For each competition in COMPETITION_MAP, fetches FINISHED matches from
    the last `days_back` days, resolves team names, and runs incremental
    update to recompute ratings.

    Args:
        db_path: Path to SQLite database. Defaults to data/elo.db.
        days_back: Number of days to look back for completed matches.
        client: Optional pre-configured FootballDataClient (for testing).

    Returns:
        Summary dict with matches_fetched, matches_ingested,
        matches_skipped, competitions_checked.
    """
    known_teams = _get_known_teams(db_path)
    rows = []
    matches_fetched = 0
    matches_skipped = 0

    close_client = client is None
    if client is None:
        client = FootballDataClient()
        await client.__aenter__()

    try:
        for comp_code in COMPETITION_MAP:
            try:
                matches = await client.get_matches(
                    competition_code=comp_code,
                    status="FINISHED",
                )
            except Exception:
                logger.warning("Failed to fetch matches for %s", comp_code)
                continue

            # Filter to recent matches only
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime(
                "%Y-%m-%d"
            )

            for match in matches:
                match_date = match["utcDate"][:10]
                if match_date < cutoff:
                    continue

                matches_fetched += 1

                api_home = match.get("homeTeam", {}).get("name")
                api_away = match.get("awayTeam", {}).get("name")

                if not api_home or not api_away:
                    logger.warning(
                        "Skipping match with TBD team(s): %s / %s",
                        api_home,
                        api_away,
                    )
                    matches_skipped += 1
                    continue

                home_name = resolve_team(api_home, known_teams)
                away_name = resolve_team(api_away, known_teams)

                if home_name is None or away_name is None:
                    skipped_teams = []
                    if home_name is None:
                        skipped_teams.append(api_home)
                    if away_name is None:
                        skipped_teams.append(api_away)
                    logger.warning(
                        "Skipping match: unresolvable team(s) %s",
                        skipped_teams,
                    )
                    matches_skipped += 1
                    continue

                row = _api_match_to_dataframe_row(
                    match, home_name, away_name, comp_code
                )
                rows.append(row)
    finally:
        if close_client:
            await client.__aexit__(None, None, None)

    summary = {
        "matches_fetched": matches_fetched,
        "matches_ingested": 0,
        "matches_skipped": matches_skipped,
        "competitions_checked": len(COMPETITION_MAP),
    }

    if not rows:
        logger.info("No new matches to ingest.")
        return summary

    new_matches_df = pd.DataFrame(rows)
    new_matches_df = new_matches_df.sort_values("Date").reset_index(drop=True)

    result = run_incremental_update(
        db_path=db_path,
        new_matches_df=new_matches_df,
        skip_validation=True,
    )
    summary["matches_ingested"] = result.get("new_matches", 0)
    return summary


async def fetch_and_ingest_fixtures(
    db_path: str | Path | None = None,
    days_ahead: int = 30,
    client: FootballDataClient | None = None,
) -> dict:
    """Fetch upcoming scheduled matches and insert as fixtures with predictions.

    For each competition in COMPETITION_MAP, fetches SCHEDULED/TIMED matches
    for the next `days_ahead` days, resolves team names, inserts into the
    fixtures table, and generates predictions.

    Args:
        db_path: Path to SQLite database. Defaults to data/elo.db.
        days_ahead: Number of days ahead to fetch fixtures.
        client: Optional pre-configured FootballDataClient (for testing).

    Returns:
        Summary dict with fixtures_fetched, fixtures_ingested,
        fixtures_skipped, predictions_generated.
    """
    known_teams = _get_known_teams(db_path)
    fixtures_fetched = 0
    fixtures_ingested = 0
    fixtures_skipped = 0
    predictions_generated = 0

    close_client = client is None
    if client is None:
        client = FootballDataClient()
        await client.__aenter__()

    # Get current ratings for predictions
    conn = init_db(db_path)
    try:
        latest_date = get_latest_match_date(conn)
        ratings = get_ratings_at_date(conn, latest_date) if latest_date else {}

        for comp_code in COMPETITION_MAP:
            comp_name = _COMPETITION_NAME_MAP.get(comp_code, comp_code)
            comp_info = COMPETITION_MAP[comp_code]

            try:
                matches = await client.get_matches(
                    competition_code=comp_code,
                    status="SCHEDULED",
                )
            except Exception:
                logger.warning("Failed to fetch fixtures for %s", comp_code)
                continue

            cutoff = (datetime.now(timezone.utc) + timedelta(days=days_ahead)).strftime(
                "%Y-%m-%d"
            )

            for match in matches:
                match_date = match["utcDate"][:10]
                if match_date > cutoff:
                    continue

                fixtures_fetched += 1

                api_home = match.get("homeTeam", {}).get("name")
                api_away = match.get("awayTeam", {}).get("name")

                if not api_home or not api_away:
                    logger.warning(
                        "Skipping fixture with TBD team(s): %s / %s",
                        api_home,
                        api_away,
                    )
                    fixtures_skipped += 1
                    continue

                home_name = resolve_team(api_home, known_teams)
                away_name = resolve_team(api_away, known_teams)

                if home_name is None or away_name is None:
                    logger.warning(
                        "Skipping fixture: unresolvable team(s) %s / %s",
                        api_home,
                        api_away,
                    )
                    fixtures_skipped += 1
                    continue

                # Ensure teams and competition exist
                comp_id = insert_competition(
                    conn,
                    comp_name,
                    tier=comp_info.get("tier", 5),
                    country=comp_info.get("country", ""),
                )
                home_id = insert_team(conn, home_name)
                away_id = insert_team(conn, away_name)

                season = _determine_season(match_date)
                external_id = str(match.get("id", ""))

                fixture_id = insert_fixture(
                    conn,
                    date=match_date,
                    home_team_id=home_id,
                    away_team_id=away_id,
                    competition_id=comp_id,
                    season=season,
                    status="scheduled",
                    external_api_id=external_id,
                )

                if fixture_id is not None:
                    fixtures_ingested += 1

                    # Generate prediction if both teams have ratings
                    if home_name in ratings and away_name in ratings:
                        try:
                            pred = predict_match(
                                home_name, away_name, ratings
                            )
                            insert_prediction(
                                conn,
                                p_home=pred["p_home"],
                                p_draw=pred["p_draw"],
                                p_away=pred["p_away"],
                                home_elo=pred["home_rating"],
                                away_elo=pred["away_rating"],
                                fixture_id=fixture_id,
                            )
                            predictions_generated += 1
                        except Exception:
                            logger.warning(
                                "Failed to predict %s vs %s",
                                home_name,
                                away_name,
                            )

            conn.commit()
    finally:
        conn.close()
        if close_client:
            await client.__aexit__(None, None, None)

    return {
        "fixtures_fetched": fixtures_fetched,
        "fixtures_ingested": fixtures_ingested,
        "fixtures_skipped": fixtures_skipped,
        "predictions_generated": predictions_generated,
    }


async def run_daily_update(db_path: str | Path | None = None) -> dict:
    """Run both match ingestion and fixture fetching.

    Convenience function that:
    1. Fetches and ingests recently completed matches (last 14 days)
    2. Fetches and inserts upcoming fixtures (next 30 days)

    Args:
        db_path: Path to SQLite database. Defaults to data/elo.db.

    Returns:
        Combined summary dict with keys from both sub-operations.
    """
    logger.info("Starting daily update...")

    matches_summary = await fetch_and_ingest_matches(db_path=db_path)
    logger.info("Matches: %s", matches_summary)

    fixtures_summary = await fetch_and_ingest_fixtures(db_path=db_path)
    logger.info("Fixtures: %s", fixtures_summary)

    return {
        "matches": matches_summary,
        "fixtures": fixtures_summary,
    }
