"""Tests for live match ingestion from football-data.org."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest
import pytest_asyncio

from src.db.connection import init_db
from src.db.repository import (
    get_match_count,
    get_upcoming_fixtures,
    insert_competition,
    insert_team,
)
from src.live.ingestion import (
    _api_match_to_dataframe_row,
    _determine_result,
    _determine_season,
    _get_known_teams,
    fetch_and_ingest_fixtures,
    fetch_and_ingest_matches,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_api_match():
    """A sample FINISHED match from the football-data.org API."""
    # Use a date close to 'today' so it passes the days_back filter
    from datetime import datetime, timedelta
    recent_date = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%dT20:00:00Z")
    return {
        "id": 12345,
        "utcDate": recent_date,
        "status": "FINISHED",
        "homeTeam": {"id": 57, "name": "Arsenal FC"},
        "awayTeam": {"id": 65, "name": "Manchester City FC"},
        "score": {
            "fullTime": {"home": 2, "away": 1},
        },
        "competition": {"code": "PL"},
        "season": {"startDate": "2025-08-01"},
    }


@pytest.fixture
def sample_api_fixture():
    """A sample SCHEDULED match from the football-data.org API."""
    return {
        "id": 99999,
        "utcDate": "2026-04-10T15:00:00Z",
        "status": "SCHEDULED",
        "homeTeam": {"id": 57, "name": "Arsenal FC"},
        "awayTeam": {"id": 65, "name": "Manchester City FC"},
        "score": {"fullTime": {"home": None, "away": None}},
        "competition": {"code": "PL"},
        "season": {"startDate": "2025-08-01"},
    }


@pytest.fixture
def mem_db():
    """In-memory SQLite database with schema applied."""
    conn = init_db(":memory:")
    yield conn
    conn.close()


def _seed_db(conn):
    """Insert basic teams and competition into test DB."""
    comp_id = insert_competition(conn, "Premier League", tier=5, country="England")
    t1 = insert_team(conn, "Arsenal", country="England")
    t2 = insert_team(conn, "Man City", country="England")
    t3 = insert_team(conn, "Liverpool", country="England")
    conn.commit()
    return comp_id, t1, t2, t3


# ---------------------------------------------------------------------------
# Unit tests: helper functions
# ---------------------------------------------------------------------------

class TestDetermineResult:
    def test_home_win(self):
        assert _determine_result(3, 1) == "H"

    def test_away_win(self):
        assert _determine_result(0, 2) == "A"

    def test_draw(self):
        assert _determine_result(1, 1) == "D"

    def test_zero_zero(self):
        assert _determine_result(0, 0) == "D"

    def test_large_score(self):
        assert _determine_result(7, 0) == "H"


class TestDetermineSeason:
    def test_august_start(self):
        assert _determine_season("2025-08-15") == "2526"

    def test_december(self):
        assert _determine_season("2025-12-26") == "2526"

    def test_january(self):
        assert _determine_season("2026-01-10") == "2526"

    def test_may(self):
        assert _determine_season("2026-05-20") == "2526"

    def test_july_previous_season(self):
        # July belongs to the previous season (ends in May/June)
        assert _determine_season("2026-07-01") == "2526"

    def test_century_boundary(self):
        assert _determine_season("2099-09-01") == "9900"


class TestApiMatchToDataframeRow:
    def test_basic_conversion(self, sample_api_match):
        row = _api_match_to_dataframe_row(
            sample_api_match, "Arsenal", "Man City", "PL"
        )
        # Date is dynamic (recent), just verify format
        assert len(row["Date"]) == 10  # YYYY-MM-DD
        assert row["HomeTeam"] == "Arsenal"
        assert row["AwayTeam"] == "Man City"
        assert row["FTHG"] == 2
        assert row["FTAG"] == 1
        assert row["FTR"] == "H"
        assert row["League"] == "Premier League"
        assert row["Competition"] == "Premier League"
        assert row["Tier"] == 5

    def test_champions_league_tier(self, sample_api_match):
        row = _api_match_to_dataframe_row(
            sample_api_match, "Arsenal", "Man City", "CL"
        )
        assert row["Tier"] == 1
        assert row["Competition"] == "Champions League"

    def test_draw_result(self):
        match_data = {
            "utcDate": "2026-03-01T20:00:00Z",
            "score": {"fullTime": {"home": 1, "away": 1}},
        }
        row = _api_match_to_dataframe_row(
            match_data, "Arsenal", "Man City", "PL"
        )
        assert row["FTR"] == "D"


# ---------------------------------------------------------------------------
# Integration tests: fetch_and_ingest_matches
# ---------------------------------------------------------------------------

class TestFetchAndIngestMatches:
    @pytest.mark.asyncio
    async def test_skips_unresolvable_teams(self, caplog):
        """Matches with unknown teams should be skipped with a warning."""
        unknown_match = {
            "id": 1,
            "utcDate": "2026-03-14T20:00:00Z",
            "status": "FINISHED",
            "homeTeam": {"id": 999, "name": "Unknown FC"},
            "awayTeam": {"id": 998, "name": "Mystery United"},
            "score": {"fullTime": {"home": 1, "away": 0}},
            "competition": {"code": "PL"},
        }
        mock_client = AsyncMock()
        mock_client.get_matches = AsyncMock(side_effect=lambda **kw:
            [unknown_match] if kw.get("competition_code") == "PL" else []
        )

        with caplog.at_level(logging.WARNING):
            with patch(
                "src.live.ingestion._get_known_teams",
                return_value=["Arsenal", "Man City"],
            ):
                summary = await fetch_and_ingest_matches(
                    db_path=":memory:",
                    days_back=14,
                    client=mock_client,
                )

        assert summary["matches_fetched"] == 1
        assert summary["matches_skipped"] == 1
        assert summary["matches_ingested"] == 0
        assert "unresolvable" in caplog.text.lower() or "Skipping" in caplog.text

    @pytest.mark.asyncio
    async def test_empty_response(self):
        """No matches returned should produce zero counts."""
        mock_client = AsyncMock()
        mock_client.get_matches = AsyncMock(return_value=[])

        with patch(
            "src.live.ingestion._get_known_teams",
            return_value=["Arsenal", "Man City"],
        ):
            summary = await fetch_and_ingest_matches(
                db_path=":memory:",
                days_back=14,
                client=mock_client,
            )

        assert summary["matches_fetched"] == 0
        assert summary["matches_ingested"] == 0
        assert summary["matches_skipped"] == 0
        assert summary["competitions_checked"] == 8  # len(COMPETITION_MAP)

    @pytest.mark.asyncio
    async def test_api_error_continues(self):
        """If one competition fails, others should still be processed."""
        call_count = 0

        async def side_effect(competition_code, status=None):
            nonlocal call_count
            call_count += 1
            if competition_code == "PL":
                raise ConnectionError("Network error")
            return []

        mock_client = AsyncMock()
        mock_client.get_matches = AsyncMock(side_effect=side_effect)

        with patch(
            "src.live.ingestion._get_known_teams",
            return_value=["Arsenal"],
        ):
            summary = await fetch_and_ingest_matches(
                db_path=":memory:",
                days_back=14,
                client=mock_client,
            )

        # Should have attempted all 8 competitions even though PL failed
        assert summary["competitions_checked"] == 8
        assert call_count == 8

    @pytest.mark.asyncio
    async def test_matches_ingested_with_mock_pipeline(self, sample_api_match):
        """Resolved matches should be passed to run_incremental_update."""
        mock_client = AsyncMock()
        mock_client.get_matches = AsyncMock(side_effect=lambda **kw:
            [sample_api_match] if kw.get("competition_code") == "PL" else []
        )

        with patch(
            "src.live.ingestion._get_known_teams",
            return_value=["Arsenal", "Man City"],
        ), patch(
            "src.live.ingestion.run_incremental_update",
            return_value={"new_matches": 1},
        ) as mock_update:
            summary = await fetch_and_ingest_matches(
                db_path=":memory:",
                days_back=30,
                client=mock_client,
            )

        assert summary["matches_fetched"] == 1
        assert summary["matches_ingested"] == 1
        # Verify the DataFrame was passed correctly
        call_args = mock_update.call_args
        df = call_args.kwargs.get("new_matches_df")
        if df is None:
            df = call_args[1].get("new_matches_df")
        assert len(df) == 1
        assert df.iloc[0]["HomeTeam"] == "Arsenal"
        assert df.iloc[0]["AwayTeam"] == "Man City"

    @pytest.mark.asyncio
    async def test_old_matches_filtered_by_days_back(self, sample_api_match):
        """Matches older than days_back should be filtered out."""
        # Set the match date to 30 days ago
        sample_api_match["utcDate"] = "2025-01-01T20:00:00Z"

        mock_client = AsyncMock()
        mock_client.get_matches = AsyncMock(side_effect=lambda **kw:
            [sample_api_match] if kw.get("competition_code") == "PL" else []
        )

        with patch(
            "src.live.ingestion._get_known_teams",
            return_value=["Arsenal", "Man City"],
        ):
            summary = await fetch_and_ingest_matches(
                db_path=":memory:",
                days_back=7,
                client=mock_client,
            )

        assert summary["matches_fetched"] == 0
        assert summary["matches_ingested"] == 0


# ---------------------------------------------------------------------------
# Integration tests: fetch_and_ingest_fixtures
# ---------------------------------------------------------------------------

class TestFetchAndIngestFixtures:
    @pytest.mark.asyncio
    async def test_fixture_ingestion(self, sample_api_fixture):
        """Fixtures should be inserted into the database."""
        mock_client = AsyncMock()
        mock_client.get_matches = AsyncMock(side_effect=lambda **kw:
            [sample_api_fixture] if kw.get("competition_code") == "PL" else []
        )

        # Use an in-memory DB with seeded teams
        conn = init_db(":memory:")
        _seed_db(conn)

        # Insert a match + rating so predictions work
        from src.db.repository import insert_match, insert_rating
        comp_row = conn.execute(
            "SELECT id FROM competitions WHERE name='Premier League'"
        ).fetchone()
        comp_id = comp_row["id"]
        t1_row = conn.execute("SELECT id FROM teams WHERE name='Arsenal'").fetchone()
        t2_row = conn.execute("SELECT id FROM teams WHERE name='Man City'").fetchone()
        match_id = insert_match(
            conn, "2026-03-01", t1_row["id"], t2_row["id"],
            2, 1, "H", comp_id, "2526"
        )
        insert_rating(conn, t1_row["id"], match_id, "2026-03-01", 1600.0, 10.0)
        insert_rating(conn, t2_row["id"], match_id, "2026-03-01", 1550.0, -10.0)
        conn.commit()

        # Verify ratings are in the DB before running
        from src.db.repository import get_ratings_at_date, get_latest_match_date
        latest = get_latest_match_date(conn)
        ratings = get_ratings_at_date(conn, latest)
        assert "Arsenal" in ratings, f"Arsenal not in ratings: {ratings}"
        assert "Man City" in ratings, f"Man City not in ratings: {ratings}"

        # We need to mock _get_known_teams and init_db to use our conn
        with patch(
            "src.live.ingestion._get_known_teams",
            return_value=["Arsenal", "Man City", "Liverpool"],
        ), patch(
            "src.live.ingestion.init_db",
            return_value=conn,
        ):
            summary = await fetch_and_ingest_fixtures(
                db_path=":memory:",
                days_ahead=60,
                client=mock_client,
            )

        assert summary["fixtures_fetched"] == 1
        assert summary["fixtures_ingested"] == 1
        assert summary["fixtures_skipped"] == 0
        assert summary["predictions_generated"] == 1

    @pytest.mark.asyncio
    async def test_fixture_skips_unknown_teams(self, sample_api_fixture):
        """Fixtures with unknown teams should be skipped."""
        sample_api_fixture["homeTeam"]["name"] = "Unknown FC"

        mock_client = AsyncMock()
        mock_client.get_matches = AsyncMock(side_effect=lambda **kw:
            [sample_api_fixture] if kw.get("competition_code") == "PL" else []
        )

        conn = init_db(":memory:")
        _seed_db(conn)

        with patch(
            "src.live.ingestion._get_known_teams",
            return_value=["Arsenal", "Man City"],
        ), patch(
            "src.live.ingestion.init_db",
            return_value=conn,
        ):
            summary = await fetch_and_ingest_fixtures(
                db_path=":memory:",
                days_ahead=60,
                client=mock_client,
            )

        assert summary["fixtures_skipped"] == 1
        assert summary["fixtures_ingested"] == 0


# ---------------------------------------------------------------------------
# Unit test: _get_known_teams
# ---------------------------------------------------------------------------

class TestGetKnownTeams:
    def test_returns_team_names(self, mem_db):
        _seed_db(mem_db)
        # We can't easily test _get_known_teams with in-memory DB since it
        # opens its own connection, so test the query pattern directly.
        rows = mem_db.execute("SELECT name FROM teams ORDER BY name").fetchall()
        names = [r["name"] for r in rows]
        assert "Arsenal" in names
        assert "Man City" in names
        assert "Liverpool" in names
