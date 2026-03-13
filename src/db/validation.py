"""Data validation checks for the Elo database."""

import sqlite3


# Expected matches per league per season (approximate — allows 10% tolerance)
EXPECTED_MATCHES_PER_SEASON = {
    "Premier League": 380,
    "La Liga": 380,
    "Serie A": 380,
    "Bundesliga": 306,
    "Ligue 1": 380,
}


def validate_database(conn: sqlite3.Connection) -> list[str]:
    """Run all validation checks.

    Args:
        conn: Active database connection.

    Returns:
        List of issue descriptions. Empty list means all checks passed.
    """
    issues: list[str] = []
    issues.extend(check_referential_integrity(conn))
    issues.extend(check_completeness(conn))
    issues.extend(check_rating_consistency(conn))
    return issues


def check_referential_integrity(conn: sqlite3.Connection) -> list[str]:
    """Check for orphaned references."""
    issues: list[str] = []

    # Matches referencing non-existent teams
    orphan_teams = conn.execute(
        """SELECT COUNT(*) as cnt FROM matches m
           WHERE m.home_team_id NOT IN (SELECT id FROM teams)
              OR m.away_team_id NOT IN (SELECT id FROM teams)"""
    ).fetchone()
    if orphan_teams["cnt"] > 0:
        issues.append(f"Matches with orphaned team references: {orphan_teams['cnt']}")

    # Matches referencing non-existent competitions
    orphan_comps = conn.execute(
        """SELECT COUNT(*) as cnt FROM matches m
           WHERE m.competition_id NOT IN (SELECT id FROM competitions)"""
    ).fetchone()
    if orphan_comps["cnt"] > 0:
        issues.append(
            f"Matches with orphaned competition references: {orphan_comps['cnt']}"
        )

    # Ratings referencing non-existent matches
    orphan_ratings = conn.execute(
        """SELECT COUNT(*) as cnt FROM ratings_history rh
           WHERE rh.match_id NOT IN (SELECT id FROM matches)"""
    ).fetchone()
    if orphan_ratings["cnt"] > 0:
        issues.append(
            f"Ratings with orphaned match references: {orphan_ratings['cnt']}"
        )

    return issues


def check_completeness(conn: sqlite3.Connection) -> list[str]:
    """Check that each league/season has a reasonable number of matches."""
    issues: list[str] = []

    rows = conn.execute(
        """SELECT c.name as competition, m.season, COUNT(*) as cnt
           FROM matches m
           JOIN competitions c ON c.id = m.competition_id
           GROUP BY c.name, m.season
           ORDER BY c.name, m.season"""
    ).fetchall()

    for row in rows:
        comp = row["competition"]
        expected = EXPECTED_MATCHES_PER_SEASON.get(comp)
        if expected is None:
            continue  # European competitions have variable match counts

        actual = row["cnt"]
        tolerance = expected * 0.1
        if actual < expected - tolerance:
            issues.append(
                f"{comp} {row['season']}: only {actual} matches "
                f"(expected ~{expected})"
            )

    return issues


def check_rating_consistency(conn: sqlite3.Connection) -> list[str]:
    """Check that ratings are within reasonable bounds."""
    issues: list[str] = []

    # Check for extreme ratings
    extremes = conn.execute(
        """SELECT t.name, rh.rating, rh.date
           FROM ratings_history rh
           JOIN teams t ON t.id = rh.team_id
           WHERE rh.rating < 800 OR rh.rating > 2200"""
    ).fetchall()

    if extremes:
        issues.append(
            f"Extreme ratings detected: {len(extremes)} entries outside [800, 2200]"
        )

    # Check for NaN/NULL ratings
    null_ratings = conn.execute(
        "SELECT COUNT(*) as cnt FROM ratings_history WHERE rating IS NULL"
    ).fetchone()
    if null_ratings["cnt"] > 0:
        issues.append(f"NULL ratings found: {null_ratings['cnt']}")

    return issues
