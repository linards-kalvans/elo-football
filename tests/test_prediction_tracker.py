"""Tests for prediction accuracy tracking with Brier scores."""

import sqlite3

import pytest
import pytest_asyncio
import aiosqlite

from src.live.prediction_tracker import (
    compute_brier_score,
    get_prediction_accuracy,
    generate_fixture_predictions,
    score_completed_matches,
)


# --- Brier score unit tests ---


class TestComputeBrierScore:
    def test_perfect_home_win_prediction(self):
        """Perfect prediction of a home win gives Brier score of 0."""
        score = compute_brier_score(1.0, 0.0, 0.0, "H")
        assert score == pytest.approx(0.0)

    def test_perfect_draw_prediction(self):
        """Perfect prediction of a draw gives Brier score of 0."""
        score = compute_brier_score(0.0, 1.0, 0.0, "D")
        assert score == pytest.approx(0.0)

    def test_perfect_away_win_prediction(self):
        """Perfect prediction of an away win gives Brier score of 0."""
        score = compute_brier_score(0.0, 0.0, 1.0, "A")
        assert score == pytest.approx(0.0)

    def test_worst_home_win_prediction(self):
        """Predicting 0% home win when home wins gives maximum Brier score."""
        # BS = (0 - 1)^2 + (0.5 - 0)^2 + (0.5 - 0)^2 = 1 + 0.25 + 0.25 = 1.5
        score = compute_brier_score(0.0, 0.5, 0.5, "H")
        assert score == pytest.approx(1.5)

    def test_absolute_worst_prediction(self):
        """Predict 100% away when home wins: BS = (0-1)^2 + (0-0)^2 + (1-0)^2 = 2."""
        score = compute_brier_score(0.0, 0.0, 1.0, "H")
        assert score == pytest.approx(2.0)

    def test_even_prediction_home_win(self):
        """Equal probabilities with home win."""
        score = compute_brier_score(1 / 3, 1 / 3, 1 / 3, "H")
        # BS = (1/3 - 1)^2 + (1/3 - 0)^2 + (1/3 - 0)^2
        expected = (1 / 3 - 1) ** 2 + (1 / 3) ** 2 + (1 / 3) ** 2
        assert score == pytest.approx(expected)

    def test_realistic_prediction_home_win(self):
        """Realistic prediction where home is favored and wins."""
        score = compute_brier_score(0.6, 0.25, 0.15, "H")
        expected = (0.6 - 1) ** 2 + (0.25 - 0) ** 2 + (0.15 - 0) ** 2
        assert score == pytest.approx(expected)

    def test_realistic_prediction_draw(self):
        """Realistic prediction where draw occurs."""
        score = compute_brier_score(0.45, 0.30, 0.25, "D")
        expected = (0.45 - 0) ** 2 + (0.30 - 1) ** 2 + (0.25 - 0) ** 2
        assert score == pytest.approx(expected)

    def test_brier_score_range(self):
        """Brier score should always be between 0 and 2."""
        for result in ["H", "D", "A"]:
            for p_h, p_d, p_a in [
                (0.5, 0.3, 0.2),
                (0.0, 0.0, 1.0),
                (1.0, 0.0, 0.0),
                (0.33, 0.34, 0.33),
            ]:
                score = compute_brier_score(p_h, p_d, p_a, result)
                assert 0 <= score <= 2


# --- Database integration tests ---



def _setup_test_db_sync(path: str):
    """Set up a test database synchronously."""
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            country TEXT NOT NULL DEFAULT '',
            aliases TEXT NOT NULL DEFAULT '[]'
        );

        CREATE TABLE IF NOT EXISTS competitions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            tier INTEGER NOT NULL DEFAULT 5,
            country TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            home_team_id INTEGER NOT NULL REFERENCES teams(id),
            away_team_id INTEGER NOT NULL REFERENCES teams(id),
            home_goals INTEGER NOT NULL,
            away_goals INTEGER NOT NULL,
            result TEXT NOT NULL CHECK (result IN ('H', 'D', 'A')),
            competition_id INTEGER NOT NULL REFERENCES competitions(id),
            season TEXT NOT NULL,
            UNIQUE(date, home_team_id, away_team_id, competition_id)
        );

        CREATE TABLE IF NOT EXISTS ratings_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL REFERENCES teams(id),
            match_id INTEGER NOT NULL REFERENCES matches(id),
            date TEXT NOT NULL,
            rating REAL NOT NULL,
            rating_delta REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS fixtures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            home_team_id INTEGER NOT NULL REFERENCES teams(id),
            away_team_id INTEGER NOT NULL REFERENCES teams(id),
            competition_id INTEGER NOT NULL REFERENCES competitions(id),
            season TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'scheduled'
                CHECK (status IN ('scheduled', 'completed', 'postponed', 'cancelled')),
            external_api_id TEXT,
            last_updated TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(date, home_team_id, away_team_id, competition_id)
        );

        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER REFERENCES matches(id),
            fixture_id INTEGER REFERENCES fixtures(id),
            predicted_at TEXT NOT NULL DEFAULT (datetime('now')),
            p_home REAL NOT NULL,
            p_draw REAL NOT NULL,
            p_away REAL NOT NULL,
            home_elo REAL NOT NULL,
            away_elo REAL NOT NULL,
            brier_score REAL,
            scored_at TEXT,
            CHECK (
                (match_id IS NOT NULL AND fixture_id IS NULL) OR
                (match_id IS NULL AND fixture_id IS NOT NULL)
            )
        );
    """)

    conn.execute("INSERT INTO teams (id, name, country) VALUES (1, 'Arsenal', 'England')")
    conn.execute("INSERT INTO teams (id, name, country) VALUES (2, 'Chelsea', 'England')")
    conn.execute("INSERT INTO teams (id, name, country) VALUES (3, 'Bayern Munich', 'Germany')")
    conn.execute("INSERT INTO teams (id, name, country) VALUES (4, 'Dortmund', 'Germany')")
    conn.execute("INSERT INTO competitions (id, name, tier, country) VALUES (1, 'Premier League', 5, 'England')")
    conn.execute("INSERT INTO competitions (id, name, tier, country) VALUES (2, 'Bundesliga', 5, 'Germany')")

    conn.execute(
        """INSERT INTO matches (id, date, home_team_id, away_team_id,
           home_goals, away_goals, result, competition_id, season)
           VALUES (1, '2025-01-15', 1, 2, 2, 1, 'H', 1, '2425')"""
    )
    conn.execute(
        """INSERT INTO matches (id, date, home_team_id, away_team_id,
           home_goals, away_goals, result, competition_id, season)
           VALUES (2, '2025-01-16', 2, 1, 0, 0, 'D', 1, '2425')"""
    )
    conn.execute(
        """INSERT INTO matches (id, date, home_team_id, away_team_id,
           home_goals, away_goals, result, competition_id, season)
           VALUES (3, '2025-01-17', 3, 4, 1, 3, 'A', 2, '2425')"""
    )

    conn.execute(
        """INSERT INTO ratings_history (team_id, match_id, date, rating, rating_delta)
           VALUES (1, 1, '2025-01-15', 1550.0, 10.0)"""
    )
    conn.execute(
        """INSERT INTO ratings_history (team_id, match_id, date, rating, rating_delta)
           VALUES (2, 1, '2025-01-15', 1480.0, -10.0)"""
    )
    conn.execute(
        """INSERT INTO ratings_history (team_id, match_id, date, rating, rating_delta)
           VALUES (3, 3, '2025-01-17', 1600.0, -15.0)"""
    )
    conn.execute(
        """INSERT INTO ratings_history (team_id, match_id, date, rating, rating_delta)
           VALUES (4, 3, '2025-01-17', 1450.0, 15.0)"""
    )

    conn.commit()
    conn.close()


@pytest.fixture
def test_db(tmp_path):
    """Create a test database with sample data."""
    db_path = str(tmp_path / "test.db")
    _setup_test_db_sync(db_path)
    return db_path


class TestScoreCompletedMatches:
    @pytest.mark.asyncio
    async def test_scores_unscored_predictions(self, test_db):
        """Score predictions that have match results but no Brier score."""
        # Insert predictions linked to matches
        conn = await aiosqlite.connect(test_db)
        await conn.execute(
            """INSERT INTO predictions (match_id, p_home, p_draw, p_away, home_elo, away_elo)
               VALUES (1, 0.6, 0.25, 0.15, 1550.0, 1480.0)"""
        )
        await conn.execute(
            """INSERT INTO predictions (match_id, p_home, p_draw, p_away, home_elo, away_elo)
               VALUES (2, 0.5, 0.3, 0.2, 1480.0, 1550.0)"""
        )
        await conn.commit()
        await conn.close()

        result = await score_completed_matches(test_db)
        assert result["scored_count"] == 2
        assert result["errors"] == 0

        # Verify Brier scores were stored
        conn = await aiosqlite.connect(test_db)
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT brier_score, scored_at FROM predictions WHERE match_id = 1"
        )
        row = await cursor.fetchone()
        assert row["brier_score"] is not None
        assert row["scored_at"] is not None

        # Match 1 result is H, prediction was (0.6, 0.25, 0.15)
        expected_brier = (0.6 - 1) ** 2 + (0.25 - 0) ** 2 + (0.15 - 0) ** 2
        assert row["brier_score"] == pytest.approx(expected_brier)
        await conn.close()

    @pytest.mark.asyncio
    async def test_does_not_rescore(self, test_db):
        """Already-scored predictions should not be rescored."""
        conn = await aiosqlite.connect(test_db)
        await conn.execute(
            """INSERT INTO predictions (match_id, p_home, p_draw, p_away,
               home_elo, away_elo, brier_score, scored_at)
               VALUES (1, 0.6, 0.25, 0.15, 1550.0, 1480.0, 0.5, '2025-01-20')"""
        )
        await conn.commit()
        await conn.close()

        result = await score_completed_matches(test_db)
        assert result["scored_count"] == 0

    @pytest.mark.asyncio
    async def test_empty_database(self, test_db):
        """No predictions to score returns zero count."""
        result = await score_completed_matches(test_db)
        assert result["scored_count"] == 0
        assert result["errors"] == 0


class TestGetPredictionAccuracy:
    @pytest.mark.asyncio
    async def test_no_scored_predictions(self, test_db):
        """Empty state returns None for aggregates."""
        result = await get_prediction_accuracy(test_db)
        assert result["total_predictions"] == 0
        assert result["mean_brier_score"] is None
        assert result["median_brier_score"] is None
        assert result["calibration"] == {}
        assert result["by_competition"] == {}
        assert result["recent_form"] is None

    @pytest.mark.asyncio
    async def test_aggregate_stats(self, test_db):
        """Test aggregate Brier score computation."""
        conn = await aiosqlite.connect(test_db)

        # Insert scored predictions
        brier1 = compute_brier_score(0.6, 0.25, 0.15, "H")
        brier2 = compute_brier_score(0.5, 0.3, 0.2, "D")
        brier3 = compute_brier_score(0.3, 0.2, 0.5, "A")

        await conn.execute(
            """INSERT INTO predictions (match_id, p_home, p_draw, p_away,
               home_elo, away_elo, brier_score, scored_at)
               VALUES (1, 0.6, 0.25, 0.15, 1550.0, 1480.0, ?, '2025-01-20')""",
            (brier1,),
        )
        await conn.execute(
            """INSERT INTO predictions (match_id, p_home, p_draw, p_away,
               home_elo, away_elo, brier_score, scored_at)
               VALUES (2, 0.5, 0.3, 0.2, 1480.0, 1550.0, ?, '2025-01-21')""",
            (brier2,),
        )
        await conn.execute(
            """INSERT INTO predictions (match_id, p_home, p_draw, p_away,
               home_elo, away_elo, brier_score, scored_at)
               VALUES (3, 0.3, 0.2, 0.5, 1600.0, 1450.0, ?, '2025-01-22')""",
            (brier3,),
        )
        await conn.commit()
        await conn.close()

        result = await get_prediction_accuracy(test_db)
        assert result["total_predictions"] == 3
        assert result["mean_brier_score"] is not None
        assert result["median_brier_score"] is not None

        expected_mean = round((brier1 + brier2 + brier3) / 3, 4)
        assert result["mean_brier_score"] == pytest.approx(expected_mean, abs=0.001)

    @pytest.mark.asyncio
    async def test_calibration_buckets(self, test_db):
        """Test calibration bucket computation."""
        conn = await aiosqlite.connect(test_db)

        brier = compute_brier_score(0.6, 0.25, 0.15, "H")
        await conn.execute(
            """INSERT INTO predictions (match_id, p_home, p_draw, p_away,
               home_elo, away_elo, brier_score, scored_at)
               VALUES (1, 0.6, 0.25, 0.15, 1550.0, 1480.0, ?, '2025-01-20')""",
            (brier,),
        )
        await conn.commit()
        await conn.close()

        result = await get_prediction_accuracy(test_db)
        calibration = result["calibration"]

        # Should have 10 buckets
        assert len(calibration) == 10
        # The 60-70% bucket should have at least one entry (p_home=0.6)
        bucket_60 = calibration["60-70%"]
        assert bucket_60["count"] >= 1

    @pytest.mark.asyncio
    async def test_by_competition(self, test_db):
        """Test per-competition breakdown."""
        conn = await aiosqlite.connect(test_db)

        brier1 = compute_brier_score(0.6, 0.25, 0.15, "H")
        brier3 = compute_brier_score(0.3, 0.2, 0.5, "A")

        await conn.execute(
            """INSERT INTO predictions (match_id, p_home, p_draw, p_away,
               home_elo, away_elo, brier_score, scored_at)
               VALUES (1, 0.6, 0.25, 0.15, 1550.0, 1480.0, ?, '2025-01-20')""",
            (brier1,),
        )
        await conn.execute(
            """INSERT INTO predictions (match_id, p_home, p_draw, p_away,
               home_elo, away_elo, brier_score, scored_at)
               VALUES (3, 0.3, 0.2, 0.5, 1600.0, 1450.0, ?, '2025-01-22')""",
            (brier3,),
        )
        await conn.commit()
        await conn.close()

        result = await get_prediction_accuracy(test_db)
        by_comp = result["by_competition"]
        assert "Premier League" in by_comp
        assert "Bundesliga" in by_comp
        assert by_comp["Premier League"]["count"] == 1
        assert by_comp["Bundesliga"]["count"] == 1

    @pytest.mark.asyncio
    async def test_competition_filter(self, test_db):
        """Test filtering by competition."""
        conn = await aiosqlite.connect(test_db)

        brier1 = compute_brier_score(0.6, 0.25, 0.15, "H")
        brier3 = compute_brier_score(0.3, 0.2, 0.5, "A")

        await conn.execute(
            """INSERT INTO predictions (match_id, p_home, p_draw, p_away,
               home_elo, away_elo, brier_score, scored_at)
               VALUES (1, 0.6, 0.25, 0.15, 1550.0, 1480.0, ?, '2025-01-20')""",
            (brier1,),
        )
        await conn.execute(
            """INSERT INTO predictions (match_id, p_home, p_draw, p_away,
               home_elo, away_elo, brier_score, scored_at)
               VALUES (3, 0.3, 0.2, 0.5, 1600.0, 1450.0, ?, '2025-01-22')""",
            (brier3,),
        )
        await conn.commit()
        await conn.close()

        result = await get_prediction_accuracy(test_db, competition="Premier League")
        assert result["total_predictions"] == 1

    @pytest.mark.asyncio
    async def test_recent_form(self, test_db):
        """Test recent form is computed over last 100 predictions."""
        conn = await aiosqlite.connect(test_db)

        brier1 = compute_brier_score(0.6, 0.25, 0.15, "H")
        await conn.execute(
            """INSERT INTO predictions (match_id, p_home, p_draw, p_away,
               home_elo, away_elo, brier_score, scored_at)
               VALUES (1, 0.6, 0.25, 0.15, 1550.0, 1480.0, ?, '2025-01-20')""",
            (brier1,),
        )
        await conn.commit()
        await conn.close()

        result = await get_prediction_accuracy(test_db)
        assert result["recent_form"] is not None
        assert result["recent_form"] == pytest.approx(round(brier1, 4))


class TestGenerateFixturePredictions:
    @pytest.mark.asyncio
    async def test_generates_for_unpredicted_fixtures(self, test_db):
        """Fixtures without predictions get new predictions."""
        conn = await aiosqlite.connect(test_db)
        # Insert a scheduled fixture
        await conn.execute(
            """INSERT INTO fixtures (id, date, home_team_id, away_team_id,
               competition_id, season, status)
               VALUES (1, '2025-02-01', 1, 2, 1, '2425', 'scheduled')"""
        )
        await conn.commit()
        await conn.close()

        count = await generate_fixture_predictions(test_db)
        assert count == 1

        # Verify prediction was inserted
        conn = await aiosqlite.connect(test_db)
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT p_home, p_draw, p_away FROM predictions WHERE fixture_id = 1"
        )
        row = await cursor.fetchone()
        assert row is not None
        assert row["p_home"] > 0
        assert row["p_draw"] > 0
        assert row["p_away"] > 0
        assert abs(row["p_home"] + row["p_draw"] + row["p_away"] - 1.0) < 0.01
        await conn.close()

    @pytest.mark.asyncio
    async def test_skips_already_predicted(self, test_db):
        """Fixtures with existing predictions are skipped."""
        conn = await aiosqlite.connect(test_db)
        await conn.execute(
            """INSERT INTO fixtures (id, date, home_team_id, away_team_id,
               competition_id, season, status)
               VALUES (1, '2025-02-01', 1, 2, 1, '2425', 'scheduled')"""
        )
        await conn.execute(
            """INSERT INTO predictions (fixture_id, p_home, p_draw, p_away,
               home_elo, away_elo)
               VALUES (1, 0.5, 0.3, 0.2, 1550.0, 1480.0)"""
        )
        await conn.commit()
        await conn.close()

        count = await generate_fixture_predictions(test_db)
        assert count == 0

    @pytest.mark.asyncio
    async def test_no_fixtures(self, test_db):
        """No fixtures returns zero."""
        count = await generate_fixture_predictions(test_db)
        assert count == 0

    @pytest.mark.asyncio
    async def test_multiple_fixtures(self, test_db):
        """Multiple fixtures are all predicted."""
        conn = await aiosqlite.connect(test_db)
        await conn.execute(
            """INSERT INTO fixtures (id, date, home_team_id, away_team_id,
               competition_id, season, status)
               VALUES (1, '2025-02-01', 1, 2, 1, '2425', 'scheduled')"""
        )
        await conn.execute(
            """INSERT INTO fixtures (id, date, home_team_id, away_team_id,
               competition_id, season, status)
               VALUES (2, '2025-02-02', 3, 4, 2, '2425', 'scheduled')"""
        )
        await conn.commit()
        await conn.close()

        count = await generate_fixture_predictions(test_db)
        assert count == 2
