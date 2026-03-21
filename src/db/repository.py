"""Query layer for the Elo rating database."""

import json
import sqlite3
from datetime import datetime

from pydantic import BaseModel


class TeamRecord(BaseModel):
    """Team with current rating."""
    id: int
    name: str
    country: str
    aliases: list[str]
    rating: float | None = None


class MatchRecord(BaseModel):
    """Match result."""
    id: int
    date: str
    home_team: str
    away_team: str
    home_goals: int
    away_goals: int
    result: str
    competition: str
    season: str


class RatingRecord(BaseModel):
    """Single rating history entry."""
    team: str
    date: str
    rating: float
    rating_delta: float


class RankingEntry(BaseModel):
    """Team ranking entry."""
    rank: int
    team: str
    rating: float
    country: str


# --- Write operations ---


def insert_team(conn: sqlite3.Connection, name: str, country: str = "",
                aliases: list[str] | None = None) -> int:
    """Insert a team, returning its ID. Returns existing ID if name exists."""
    aliases_json = json.dumps(aliases or [])
    try:
        cur = conn.execute(
            "INSERT INTO teams (name, country, aliases) VALUES (?, ?, ?)",
            (name, country, aliases_json),
        )
        return cur.lastrowid
    except sqlite3.IntegrityError:
        row = conn.execute("SELECT id FROM teams WHERE name = ?", (name,)).fetchone()
        return row["id"]


def insert_competition(conn: sqlite3.Connection, name: str, tier: int = 5,
                       country: str = "") -> int:
    """Insert a competition, returning its ID. Returns existing ID if name exists."""
    try:
        cur = conn.execute(
            "INSERT INTO competitions (name, tier, country) VALUES (?, ?, ?)",
            (name, tier, country),
        )
        return cur.lastrowid
    except sqlite3.IntegrityError:
        row = conn.execute(
            "SELECT id FROM competitions WHERE name = ?", (name,)
        ).fetchone()
        return row["id"]


def insert_match(conn: sqlite3.Connection, date: str, home_team_id: int,
                 away_team_id: int, home_goals: int, away_goals: int,
                 result: str, competition_id: int, season: str) -> int | None:
    """Insert a match. Returns match ID, or None if duplicate."""
    try:
        cur = conn.execute(
            """INSERT INTO matches
               (date, home_team_id, away_team_id, home_goals, away_goals,
                result, competition_id, season)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (date, home_team_id, away_team_id, home_goals, away_goals,
             result, competition_id, season),
        )
        return cur.lastrowid
    except sqlite3.IntegrityError:
        return None  # Duplicate match


def insert_rating(conn: sqlite3.Connection, team_id: int, match_id: int,
                  date: str, rating: float, rating_delta: float) -> int:
    """Insert a rating history entry."""
    cur = conn.execute(
        """INSERT INTO ratings_history (team_id, match_id, date, rating, rating_delta)
           VALUES (?, ?, ?, ?, ?)""",
        (team_id, match_id, date, rating, rating_delta),
    )
    return cur.lastrowid


def insert_ratings_batch(conn: sqlite3.Connection,
                         rows: list[tuple[int, int, str, float, float]]) -> int:
    """Bulk insert rating history entries. Returns count inserted."""
    conn.executemany(
        """INSERT INTO ratings_history (team_id, match_id, date, rating, rating_delta)
           VALUES (?, ?, ?, ?, ?)""",
        rows,
    )
    return len(rows)


def insert_parameters(conn: sqlite3.Connection, k_factor: float,
                      home_advantage: float, decay_rate: float,
                      promoted_elo: float, spread: float,
                      matches_processed: int) -> int:
    """Record a parameter snapshot."""
    cur = conn.execute(
        """INSERT INTO parameters
           (run_timestamp, k_factor, home_advantage, decay_rate,
            promoted_elo, spread, matches_processed)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (datetime.now().isoformat(), k_factor, home_advantage, decay_rate,
         promoted_elo, spread, matches_processed),
    )
    return cur.lastrowid


# --- Read operations ---


def get_current_rankings(conn: sqlite3.Connection,
                         limit: int = 50) -> list[RankingEntry]:
    """Get current team rankings based on latest rating per team."""
    rows = conn.execute(
        """SELECT t.name, t.country, rh.rating
           FROM ratings_history rh
           JOIN teams t ON t.id = rh.team_id
           WHERE rh.id IN (
               SELECT id FROM ratings_history rh2
               WHERE rh2.team_id = rh.team_id
               ORDER BY rh2.date DESC, rh2.id DESC
               LIMIT 1
           )
           ORDER BY rh.rating DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()

    return [
        RankingEntry(rank=i + 1, team=row["name"], rating=row["rating"],
                     country=row["country"])
        for i, row in enumerate(rows)
    ]


def get_team_history(conn: sqlite3.Connection, team_name: str,
                     limit: int = 500) -> list[RatingRecord]:
    """Get rating history for a team."""
    rows = conn.execute(
        """SELECT t.name, rh.date, rh.rating, rh.rating_delta
           FROM ratings_history rh
           JOIN teams t ON t.id = rh.team_id
           WHERE t.name = ?
           ORDER BY rh.date ASC, rh.id ASC
           LIMIT ?""",
        (team_name, limit),
    ).fetchall()

    return [
        RatingRecord(team=row["name"], date=row["date"], rating=row["rating"],
                     rating_delta=row["rating_delta"])
        for row in rows
    ]


def get_ratings_at_date(conn: sqlite3.Connection,
                        date: str) -> dict[str, float]:
    """Get all team ratings as of a specific date.

    Returns the most recent rating on or before the given date for each team.
    """
    rows = conn.execute(
        """SELECT t.name, rh.rating
           FROM ratings_history rh
           JOIN teams t ON t.id = rh.team_id
           WHERE rh.id IN (
               SELECT rh2.id FROM ratings_history rh2
               WHERE rh2.team_id = rh.team_id AND rh2.date <= ?
               ORDER BY rh2.date DESC, rh2.id DESC
               LIMIT 1
           )""",
        (date,),
    ).fetchall()

    return {row["name"]: row["rating"] for row in rows}


def search_teams(conn: sqlite3.Connection, query: str,
                 limit: int = 10) -> list[TeamRecord]:
    """Search teams by name or alias using FTS5."""
    # Append * for prefix matching (e.g. "bay" matches "Bayern")
    fts_query = f"{query}*"
    rows = conn.execute(
        """SELECT t.id, t.name, t.country, t.aliases
           FROM teams_fts
           JOIN teams t ON t.id = teams_fts.rowid
           WHERE teams_fts MATCH ?
           ORDER BY rank
           LIMIT ?""",
        (fts_query, limit),
    ).fetchall()

    return [
        TeamRecord(id=row["id"], name=row["name"], country=row["country"],
                   aliases=json.loads(row["aliases"]))
        for row in rows
    ]


def get_team_by_name(conn: sqlite3.Connection, name: str) -> TeamRecord | None:
    """Look up a team by exact name."""
    row = conn.execute(
        "SELECT id, name, country, aliases FROM teams WHERE name = ?",
        (name,),
    ).fetchone()
    if row is None:
        return None
    return TeamRecord(id=row["id"], name=row["name"], country=row["country"],
                      aliases=json.loads(row["aliases"]))


def get_match_count(conn: sqlite3.Connection) -> int:
    """Get total number of matches in the database."""
    row = conn.execute("SELECT COUNT(*) as cnt FROM matches").fetchone()
    return row["cnt"]


def get_team_count(conn: sqlite3.Connection) -> int:
    """Get total number of teams in the database."""
    row = conn.execute("SELECT COUNT(*) as cnt FROM teams").fetchone()
    return row["cnt"]


def get_latest_match_date(conn: sqlite3.Connection) -> str | None:
    """Get the date of the most recent match."""
    row = conn.execute("SELECT MAX(date) as max_date FROM matches").fetchone()
    return row["max_date"]


# --- Fixtures ---


def insert_fixture(conn: sqlite3.Connection, date: str, home_team_id: int,
                   away_team_id: int, competition_id: int, season: str = "",
                   status: str = "scheduled",
                   external_api_id: str | None = None) -> int | None:
    """Insert a fixture. Returns fixture ID, or None if duplicate."""
    try:
        cur = conn.execute(
            """INSERT INTO fixtures
               (date, home_team_id, away_team_id, competition_id, season,
                status, external_api_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (date, home_team_id, away_team_id, competition_id, season,
             status, external_api_id),
        )
        return cur.lastrowid
    except sqlite3.IntegrityError:
        return None


def get_upcoming_fixtures(conn: sqlite3.Connection,
                          days_ahead: int = 7) -> list[dict]:
    """Get upcoming scheduled fixtures within the given number of days."""
    rows = conn.execute(
        """SELECT f.id, f.date, f.status, f.season, f.external_api_id,
                  th.name as home_team, ta.name as away_team,
                  c.name as competition,
                  f.home_team_id, f.away_team_id
           FROM fixtures f
           JOIN teams th ON th.id = f.home_team_id
           JOIN teams ta ON ta.id = f.away_team_id
           JOIN competitions c ON c.id = f.competition_id
           WHERE f.status = 'scheduled'
             AND f.date >= date('now')
             AND f.date <= date('now', '+' || ? || ' days')
           ORDER BY f.date ASC""",
        (days_ahead,),
    ).fetchall()

    return [
        {
            "id": row["id"],
            "date": row["date"],
            "home_team": row["home_team"],
            "away_team": row["away_team"],
            "competition": row["competition"],
            "status": row["status"],
            "season": row["season"],
            "external_api_id": row["external_api_id"],
            "home_team_id": row["home_team_id"],
            "away_team_id": row["away_team_id"],
        }
        for row in rows
    ]


def update_fixture_status(conn: sqlite3.Connection, fixture_id: int,
                           status: str) -> bool:
    """Update fixture status. Returns True if row was updated."""
    cur = conn.execute(
        "UPDATE fixtures SET status = ?, last_updated = datetime('now') WHERE id = ?",
        (status, fixture_id),
    )
    return cur.rowcount > 0


# --- Predictions ---


def insert_prediction(conn: sqlite3.Connection, p_home: float, p_draw: float,
                      p_away: float, home_elo: float, away_elo: float,
                      match_id: int | None = None,
                      fixture_id: int | None = None,
                      source: str = "live") -> int:
    """Insert a prediction. Exactly one of match_id/fixture_id must be set."""
    cur = conn.execute(
        """INSERT INTO predictions
           (match_id, fixture_id, p_home, p_draw, p_away, home_elo, away_elo,
            source)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (match_id, fixture_id, p_home, p_draw, p_away, home_elo, away_elo,
         source),
    )
    return cur.lastrowid


def get_predictions_for_fixture(conn: sqlite3.Connection,
                                 fixture_id: int) -> list[dict]:
    """Get all predictions for a fixture."""
    rows = conn.execute(
        """SELECT id, predicted_at, p_home, p_draw, p_away, home_elo, away_elo
           FROM predictions
           WHERE fixture_id = ?
           ORDER BY predicted_at DESC""",
        (fixture_id,),
    ).fetchall()

    return [
        {
            "id": row["id"],
            "predicted_at": row["predicted_at"],
            "p_home": row["p_home"],
            "p_draw": row["p_draw"],
            "p_away": row["p_away"],
            "home_elo": row["home_elo"],
            "away_elo": row["away_elo"],
        }
        for row in rows
    ]
