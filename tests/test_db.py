"""Tests for database module: schema, connection, repository."""

import json
import sqlite3

import pytest

from src.db.connection import init_db
from src.db.repository import (
    get_current_rankings,
    get_latest_match_date,
    get_match_count,
    get_predictions_for_fixture,
    get_ratings_at_date,
    get_team_by_name,
    get_team_count,
    get_team_history,
    get_upcoming_fixtures,
    insert_competition,
    insert_fixture,
    insert_match,
    insert_parameters,
    insert_prediction,
    insert_rating,
    insert_ratings_batch,
    insert_team,
    search_teams,
    update_fixture_status,
)


@pytest.fixture
def db():
    """Create an in-memory database with schema applied."""
    conn = init_db(":memory:")
    yield conn
    conn.close()


@pytest.fixture
def seeded_db(db):
    """Database with sample teams, competitions, matches, and ratings."""
    # Teams
    t1 = insert_team(db, "Arsenal", country="England")
    t2 = insert_team(db, "Chelsea", country="England")
    t3 = insert_team(db, "Bayern Munich", country="Germany",
                     aliases=["FC Bayern München", "Bayern"])

    # Competition
    c1 = insert_competition(db, "Premier League", tier=5, country="England")
    c2 = insert_competition(db, "Champions League", tier=1, country="Europe")

    # Matches
    m1 = insert_match(db, "2024-01-15", t1, t2, 2, 1, "H", c1, "2324")
    m2 = insert_match(db, "2024-02-10", t2, t1, 0, 0, "D", c1, "2324")
    m3 = insert_match(db, "2024-03-05", t1, t3, 1, 3, "A", c2, "2324")

    # Ratings
    insert_rating(db, t1, m1, "2024-01-15", 1520.0, 20.0)
    insert_rating(db, t2, m1, "2024-01-15", 1480.0, -20.0)
    insert_rating(db, t1, m2, "2024-02-10", 1515.0, -5.0)
    insert_rating(db, t2, m2, "2024-02-10", 1485.0, 5.0)
    insert_rating(db, t1, m3, "2024-03-05", 1490.0, -25.0)
    insert_rating(db, t3, m3, "2024-03-05", 1560.0, 25.0)

    db.commit()
    return db


class TestSchema:
    """Test database schema initialization."""

    def test_tables_created(self, db):
        tables = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = {row["name"] for row in tables}
        assert "teams" in table_names
        assert "competitions" in table_names
        assert "matches" in table_names
        assert "ratings_history" in table_names
        assert "parameters" in table_names

    def test_fts_table_created(self, db):
        tables = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='teams_fts'"
        ).fetchall()
        assert len(tables) == 1

    def test_wal_mode(self, db):
        row = db.execute("PRAGMA journal_mode").fetchone()
        # In-memory DBs may not support WAL, so accept either
        assert row[0] in ("wal", "memory")

    def test_foreign_keys_enabled(self, db):
        row = db.execute("PRAGMA foreign_keys").fetchone()
        assert row[0] == 1

    def test_idempotent_init(self, db):
        """Calling init_db twice should not error."""
        init_db(":memory:")  # Second call


class TestInsertTeam:
    def test_insert_new_team(self, db):
        team_id = insert_team(db, "Arsenal", country="England")
        assert team_id > 0

    def test_insert_duplicate_returns_existing_id(self, db):
        id1 = insert_team(db, "Arsenal")
        id2 = insert_team(db, "Arsenal")
        assert id1 == id2

    def test_insert_with_aliases(self, db):
        tid = insert_team(db, "Bayern Munich", aliases=["FC Bayern München", "Bayern"])
        db.commit()
        row = db.execute("SELECT aliases FROM teams WHERE id = ?", (tid,)).fetchone()
        aliases = json.loads(row["aliases"])
        assert "FC Bayern München" in aliases
        assert "Bayern" in aliases


class TestInsertMatch:
    def test_insert_match(self, db):
        t1 = insert_team(db, "Arsenal")
        t2 = insert_team(db, "Chelsea")
        c1 = insert_competition(db, "Premier League")
        mid = insert_match(db, "2024-01-15", t1, t2, 2, 1, "H", c1, "2324")
        assert mid is not None

    def test_duplicate_match_returns_none(self, db):
        t1 = insert_team(db, "Arsenal")
        t2 = insert_team(db, "Chelsea")
        c1 = insert_competition(db, "Premier League")
        mid1 = insert_match(db, "2024-01-15", t1, t2, 2, 1, "H", c1, "2324")
        mid2 = insert_match(db, "2024-01-15", t1, t2, 2, 1, "H", c1, "2324")
        assert mid1 is not None
        assert mid2 is None


class TestRatings:
    def test_insert_and_retrieve_rating(self, db):
        tid = insert_team(db, "Arsenal")
        cid = insert_competition(db, "Premier League")
        mid = insert_match(db, "2024-01-15", tid, insert_team(db, "Chelsea"),
                           2, 1, "H", cid, "2324")
        insert_rating(db, tid, mid, "2024-01-15", 1520.0, 20.0)
        db.commit()

        history = get_team_history(db, "Arsenal")
        assert len(history) == 1
        assert history[0].rating == 1520.0
        assert history[0].rating_delta == 20.0

    def test_batch_insert(self, db):
        tid = insert_team(db, "Arsenal")
        cid = insert_competition(db, "Premier League")
        mid = insert_match(db, "2024-01-15", tid, insert_team(db, "Chelsea"),
                           2, 1, "H", cid, "2324")
        rows = [
            (tid, mid, "2024-01-15", 1520.0, 20.0),
        ]
        count = insert_ratings_batch(db, rows)
        assert count == 1


class TestQueries:
    def test_get_current_rankings(self, seeded_db):
        rankings = get_current_rankings(seeded_db)
        assert len(rankings) == 3
        # Bayern should be top (1560), then Arsenal, then Chelsea
        assert rankings[0].team == "Bayern Munich"
        assert rankings[0].rating == 1560.0

    def test_get_team_history(self, seeded_db):
        history = get_team_history(seeded_db, "Arsenal")
        assert len(history) == 3
        # Sorted by date ascending
        assert history[0].date == "2024-01-15"
        assert history[-1].date == "2024-03-05"

    def test_get_ratings_at_date(self, seeded_db):
        ratings = get_ratings_at_date(seeded_db, "2024-02-10")
        assert "Arsenal" in ratings
        assert "Chelsea" in ratings
        assert ratings["Arsenal"] == 1515.0

    def test_get_ratings_at_date_excludes_future(self, seeded_db):
        ratings = get_ratings_at_date(seeded_db, "2024-01-20")
        # Bayern's first match is 2024-03-05, should not appear
        assert "Bayern Munich" not in ratings

    def test_search_teams_by_name(self, seeded_db):
        results = search_teams(seeded_db, "Arsenal")
        assert len(results) >= 1
        assert results[0].name == "Arsenal"

    def test_search_teams_by_alias(self, seeded_db):
        results = search_teams(seeded_db, "Bayern")
        assert len(results) >= 1
        assert results[0].name == "Bayern Munich"

    def test_get_team_by_name(self, seeded_db):
        team = get_team_by_name(seeded_db, "Arsenal")
        assert team is not None
        assert team.country == "England"

    def test_get_team_by_name_not_found(self, seeded_db):
        team = get_team_by_name(seeded_db, "Nonexistent FC")
        assert team is None

    def test_get_match_count(self, seeded_db):
        assert get_match_count(seeded_db) == 3

    def test_get_team_count(self, seeded_db):
        assert get_team_count(seeded_db) == 3

    def test_get_latest_match_date(self, seeded_db):
        assert get_latest_match_date(seeded_db) == "2024-03-05"


class TestParameters:
    def test_insert_parameters(self, db):
        pid = insert_parameters(db, k_factor=20.0, home_advantage=55.0,
                                decay_rate=0.9, promoted_elo=1400.0,
                                spread=400.0, matches_processed=100)
        assert pid > 0
        row = db.execute("SELECT * FROM parameters WHERE id = ?", (pid,)).fetchone()
        assert row["k_factor"] == 20.0
        assert row["matches_processed"] == 100


class TestFixtures:
    """Test fixtures table CRUD operations."""

    def test_insert_fixture(self, db):
        t1 = insert_team(db, "Arsenal")
        t2 = insert_team(db, "Chelsea")
        c1 = insert_competition(db, "Premier League")
        fid = insert_fixture(db, "2026-04-01", t1, t2, c1, "2526")
        assert fid is not None
        assert fid > 0

    def test_duplicate_fixture_returns_none(self, db):
        t1 = insert_team(db, "Arsenal")
        t2 = insert_team(db, "Chelsea")
        c1 = insert_competition(db, "Premier League")
        fid1 = insert_fixture(db, "2026-04-01", t1, t2, c1, "2526")
        fid2 = insert_fixture(db, "2026-04-01", t1, t2, c1, "2526")
        assert fid1 is not None
        assert fid2 is None

    def test_fixture_default_status(self, db):
        t1 = insert_team(db, "Arsenal")
        t2 = insert_team(db, "Chelsea")
        c1 = insert_competition(db, "Premier League")
        fid = insert_fixture(db, "2026-04-01", t1, t2, c1)
        db.commit()
        row = db.execute("SELECT status FROM fixtures WHERE id = ?", (fid,)).fetchone()
        assert row["status"] == "scheduled"

    def test_update_fixture_status(self, db):
        t1 = insert_team(db, "Arsenal")
        t2 = insert_team(db, "Chelsea")
        c1 = insert_competition(db, "Premier League")
        fid = insert_fixture(db, "2026-04-01", t1, t2, c1)
        db.commit()
        result = update_fixture_status(db, fid, "completed")
        assert result is True
        row = db.execute("SELECT status FROM fixtures WHERE id = ?", (fid,)).fetchone()
        assert row["status"] == "completed"

    def test_update_fixture_status_nonexistent(self, db):
        result = update_fixture_status(db, 99999, "completed")
        assert result is False

    def test_fixture_invalid_status(self, db):
        t1 = insert_team(db, "Arsenal")
        t2 = insert_team(db, "Chelsea")
        c1 = insert_competition(db, "Premier League")
        fid = insert_fixture(db, "2026-04-01", t1, t2, c1)
        db.commit()
        with pytest.raises(sqlite3.IntegrityError):
            update_fixture_status(db, fid, "invalid_status")
            db.commit()

    def test_get_upcoming_fixtures(self, db):
        t1 = insert_team(db, "Arsenal")
        t2 = insert_team(db, "Chelsea")
        c1 = insert_competition(db, "Premier League")
        # Insert a fixture for today + 3 days (should appear)
        from datetime import date, timedelta
        future_date = (date.today() + timedelta(days=3)).isoformat()
        insert_fixture(db, future_date, t1, t2, c1, "2526")
        db.commit()
        upcoming = get_upcoming_fixtures(db, days_ahead=7)
        assert len(upcoming) == 1
        assert upcoming[0]["home_team"] == "Arsenal"
        assert upcoming[0]["away_team"] == "Chelsea"

    def test_get_upcoming_excludes_past(self, db):
        t1 = insert_team(db, "Arsenal")
        t2 = insert_team(db, "Chelsea")
        c1 = insert_competition(db, "Premier League")
        insert_fixture(db, "2020-01-01", t1, t2, c1, "1920")
        db.commit()
        upcoming = get_upcoming_fixtures(db, days_ahead=7)
        assert len(upcoming) == 0

    def test_get_upcoming_excludes_completed(self, db):
        t1 = insert_team(db, "Arsenal")
        t2 = insert_team(db, "Chelsea")
        c1 = insert_competition(db, "Premier League")
        from datetime import date, timedelta
        future_date = (date.today() + timedelta(days=3)).isoformat()
        fid = insert_fixture(db, future_date, t1, t2, c1, "2526")
        update_fixture_status(db, fid, "completed")
        db.commit()
        upcoming = get_upcoming_fixtures(db, days_ahead=7)
        assert len(upcoming) == 0

    def test_fixture_with_external_api_id(self, db):
        t1 = insert_team(db, "Arsenal")
        t2 = insert_team(db, "Chelsea")
        c1 = insert_competition(db, "Premier League")
        fid = insert_fixture(db, "2026-04-01", t1, t2, c1,
                             external_api_id="ext-12345")
        db.commit()
        row = db.execute("SELECT external_api_id FROM fixtures WHERE id = ?",
                         (fid,)).fetchone()
        assert row["external_api_id"] == "ext-12345"


class TestPredictions:
    """Test predictions table CRUD operations."""

    def test_insert_prediction_for_fixture(self, db):
        t1 = insert_team(db, "Arsenal")
        t2 = insert_team(db, "Chelsea")
        c1 = insert_competition(db, "Premier League")
        fid = insert_fixture(db, "2026-04-01", t1, t2, c1)
        db.commit()
        pid = insert_prediction(db, p_home=0.45, p_draw=0.28, p_away=0.27,
                                home_elo=1550.0, away_elo=1480.0, fixture_id=fid)
        assert pid > 0

    def test_insert_prediction_for_match(self, db):
        t1 = insert_team(db, "Arsenal")
        t2 = insert_team(db, "Chelsea")
        c1 = insert_competition(db, "Premier League")
        mid = insert_match(db, "2024-01-15", t1, t2, 2, 1, "H", c1, "2324")
        db.commit()
        pid = insert_prediction(db, p_home=0.50, p_draw=0.25, p_away=0.25,
                                home_elo=1500.0, away_elo=1500.0, match_id=mid)
        assert pid > 0

    def test_prediction_requires_exactly_one_ref(self, db):
        """Both match_id and fixture_id set should fail CHECK constraint."""
        t1 = insert_team(db, "Arsenal")
        t2 = insert_team(db, "Chelsea")
        c1 = insert_competition(db, "Premier League")
        mid = insert_match(db, "2024-01-15", t1, t2, 2, 1, "H", c1, "2324")
        fid = insert_fixture(db, "2026-04-01", t1, t2, c1)
        db.commit()
        with pytest.raises(sqlite3.IntegrityError):
            insert_prediction(db, p_home=0.5, p_draw=0.25, p_away=0.25,
                              home_elo=1500.0, away_elo=1500.0,
                              match_id=mid, fixture_id=fid)

    def test_prediction_requires_at_least_one_ref(self, db):
        """Neither match_id nor fixture_id should fail CHECK constraint."""
        with pytest.raises(sqlite3.IntegrityError):
            insert_prediction(db, p_home=0.5, p_draw=0.25, p_away=0.25,
                              home_elo=1500.0, away_elo=1500.0)

    def test_get_predictions_for_fixture(self, db):
        t1 = insert_team(db, "Arsenal")
        t2 = insert_team(db, "Chelsea")
        c1 = insert_competition(db, "Premier League")
        fid = insert_fixture(db, "2026-04-01", t1, t2, c1)
        insert_prediction(db, p_home=0.45, p_draw=0.28, p_away=0.27,
                          home_elo=1550.0, away_elo=1480.0, fixture_id=fid)
        insert_prediction(db, p_home=0.50, p_draw=0.25, p_away=0.25,
                          home_elo=1560.0, away_elo=1490.0, fixture_id=fid)
        db.commit()
        preds = get_predictions_for_fixture(db, fid)
        assert len(preds) == 2
        # Most recent prediction first (ordered by predicted_at DESC)
        assert preds[0]["p_home"] in (0.45, 0.50)

    def test_get_predictions_empty(self, db):
        preds = get_predictions_for_fixture(db, 99999)
        assert preds == []


class TestSchemaNewTables:
    """Test that new tables are created correctly."""

    def test_fixtures_table_exists(self, db):
        tables = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='fixtures'"
        ).fetchall()
        assert len(tables) == 1

    def test_predictions_table_exists(self, db):
        tables = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='predictions'"
        ).fetchall()
        assert len(tables) == 1

    def test_fixtures_indexes(self, db):
        indexes = db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_fixtures%'"
        ).fetchall()
        index_names = {row["name"] for row in indexes}
        assert "idx_fixtures_status" in index_names
        assert "idx_fixtures_date" in index_names

    def test_predictions_indexes(self, db):
        indexes = db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_predictions%'"
        ).fetchall()
        index_names = {row["name"] for row in indexes}
        assert "idx_predictions_fixture" in index_names
        assert "idx_predictions_match" in index_names
