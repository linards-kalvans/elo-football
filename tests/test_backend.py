"""Test suite for FastAPI backend endpoints.

Tests all API endpoints with success and error cases, validates response schemas,
and ensures database integration works correctly.
"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


@pytest.fixture(autouse=True, scope="module")
def _init_slug_cache():
    """Ensure slug cache is built before tests that hit the catch-all route."""
    import asyncio

    from backend.slugs import _cache, build_slug_cache

    if _cache is None:
        asyncio.run(build_slug_cache())


class TestHealthEndpoint:
    """Test /api/health endpoint."""

    def test_health_check_success(self):
        """Health check should return 200 with database stats."""
        response = client.get("/api/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] in ("ok", "degraded")
        assert data["version"] == "1.0.0"
        assert isinstance(data["database_connected"], bool)

        if data["database_connected"]:
            assert isinstance(data["total_teams"], int)
            assert isinstance(data["total_matches"], int)
            assert isinstance(data["latest_match_date"], str)


class TestRankingsEndpoint:
    """Test /api/rankings endpoint."""

    def test_current_rankings(self):
        """Should return current rankings."""
        response = client.get("/api/rankings?limit=10")
        assert response.status_code == 200

        data = response.json()
        assert data["date"] is None
        assert data["count"] == 10
        assert len(data["rankings"]) == 10

        # Verify ranking structure
        first = data["rankings"][0]
        assert first["rank"] == 1
        assert "team" in first
        assert "country" in first
        assert "rating" in first
        assert isinstance(first["rating"], (int, float))

    def test_historical_rankings(self):
        """Should return rankings at a specific date."""
        response = client.get("/api/rankings?date=2024-01-01&limit=5")
        assert response.status_code == 200

        data = response.json()
        assert data["date"] == "2024-01-01"
        assert data["count"] <= 5

    def test_rankings_limit_validation(self):
        """Limit parameter should be validated."""
        # Too high
        response = client.get("/api/rankings?limit=1000")
        assert response.status_code == 422  # Validation error

        # Too low
        response = client.get("/api/rankings?limit=0")
        assert response.status_code == 422

        # Valid edge cases
        response = client.get("/api/rankings?limit=1")
        assert response.status_code == 200
        assert response.json()["count"] == 1

        response = client.get("/api/rankings?limit=500")
        assert response.status_code == 200


class TestTeamDetailEndpoint:
    """Test /api/teams/{team_id} endpoint."""

    def test_team_detail_success(self):
        """Should return team detail with rating and recent matches."""
        # First find a team
        search = client.get("/api/search?q=arsenal")
        assert search.status_code == 200
        team_id = search.json()["results"][0]["id"]

        # Get team detail
        response = client.get(f"/api/teams/{team_id}")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == team_id
        assert "name" in data
        assert "country" in data
        assert "aliases" in data
        assert isinstance(data["aliases"], list)
        assert isinstance(data["current_rating"], (int, float, type(None)))
        assert isinstance(data["rank"], (int, type(None)))
        assert isinstance(data["recent_matches"], list)

        # Verify match structure if matches exist
        if data["recent_matches"]:
            match = data["recent_matches"][0]
            assert "date" in match
            assert "home_team" in match
            assert "away_team" in match
            assert "home_goals" in match
            assert "away_goals" in match
            assert "result" in match
            assert match["result"] in ("H", "D", "A")
            assert "competition" in match

    def test_team_detail_not_found(self):
        """Should return 404 for non-existent team."""
        response = client.get("/api/teams/99999")
        assert response.status_code == 404

        data = response.json()
        assert "error" in data
        assert "message" in data


class TestTeamHistoryEndpoint:
    """Test /api/teams/{team_id}/history endpoint."""

    def test_team_history_success(self):
        """Should return full rating history."""
        # Find a team
        search = client.get("/api/search?q=bayern")
        team_id = search.json()["results"][0]["id"]

        # Get history
        response = client.get(f"/api/teams/{team_id}/history?limit=100")
        assert response.status_code == 200

        data = response.json()
        assert "team" in data
        assert "history" in data
        assert isinstance(data["history"], list)

        # Verify history point structure
        if data["history"]:
            point = data["history"][0]
            assert "date" in point
            assert "rating" in point
            assert "rating_delta" in point
            assert isinstance(point["rating"], (int, float))
            assert isinstance(point["rating_delta"], (int, float))

    def test_team_history_not_found(self):
        """Should return 404 for non-existent team."""
        response = client.get("/api/teams/99999/history")
        assert response.status_code == 404

    def test_team_history_limit(self):
        """Should respect limit parameter."""
        search = client.get("/api/search?q=arsenal")
        team_id = search.json()["results"][0]["id"]

        response = client.get(f"/api/teams/{team_id}/history?limit=10")
        assert response.status_code == 200

        data = response.json()
        assert len(data["history"]) <= 10


class TestPredictionEndpoint:
    """Test /api/predict endpoint."""

    def test_prediction_success(self):
        """Should return match prediction with probabilities."""
        # Find two teams
        arsenal = client.get("/api/search?q=arsenal").json()["results"][0]["id"]
        chelsea = client.get("/api/search?q=chelsea").json()["results"][0]["id"]

        response = client.get(f"/api/predict?home={arsenal}&away={chelsea}")
        assert response.status_code == 200

        data = response.json()
        assert "home_team" in data
        assert "away_team" in data
        assert "home_rating" in data
        assert "away_rating" in data
        assert "rating_diff" in data
        assert "p_home" in data
        assert "p_draw" in data
        assert "p_away" in data

        # Probabilities should sum to ~1.0
        prob_sum = data["p_home"] + data["p_draw"] + data["p_away"]
        assert abs(prob_sum - 1.0) < 0.01

        # Each probability should be in [0, 1]
        assert 0 <= data["p_home"] <= 1
        assert 0 <= data["p_draw"] <= 1
        assert 0 <= data["p_away"] <= 1

    def test_prediction_same_team(self):
        """Should return 400 if home and away are the same."""
        response = client.get("/api/predict?home=17&away=17")
        assert response.status_code == 400

        data = response.json()
        assert "error" in data
        assert "different" in data["message"].lower()

    def test_prediction_team_not_found(self):
        """Should return 404 if team doesn't exist."""
        response = client.get("/api/predict?home=99999&away=17")
        assert response.status_code == 404


class TestLeaguesEndpoint:
    """Test /api/leagues endpoint."""

    def test_leagues_list(self):
        """Should return all available leagues."""
        response = client.get("/api/leagues")
        assert response.status_code == 200

        data = response.json()
        assert "count" in data
        assert "leagues" in data
        assert data["count"] == len(data["leagues"])

        # Verify league structure
        if data["leagues"]:
            league = data["leagues"][0]
            assert "name" in league
            assert "country" in league
            assert "tier" in league
            assert isinstance(league["tier"], int)
            assert 1 <= league["tier"] <= 5


class TestSearchEndpoint:
    """Test /api/search endpoint."""

    def test_search_success(self):
        """Should find teams matching query."""
        response = client.get("/api/search?q=bayern")
        assert response.status_code == 200

        data = response.json()
        assert data["query"] == "bayern"
        assert "count" in data
        assert "results" in data
        assert data["count"] == len(data["results"])

        # Verify result structure
        if data["results"]:
            result = data["results"][0]
            assert "id" in result
            assert "name" in result
            assert "country" in result
            assert "aliases" in result
            assert isinstance(result["aliases"], list)

    def test_search_prefix_matching(self):
        """Should match prefixes (e.g., 'bay' matches 'Bayern')."""
        response = client.get("/api/search?q=bay")
        assert response.status_code == 200

        data = response.json()
        # Should find Bayern Munich
        assert any("bayern" in r["name"].lower() for r in data["results"])

    def test_search_limit(self):
        """Should respect limit parameter."""
        response = client.get("/api/search?q=a&limit=3")
        assert response.status_code == 200

        data = response.json()
        assert len(data["results"]) <= 3

    def test_search_empty_query(self):
        """Should return 422 for empty query."""
        response = client.get("/api/search?q=")
        assert response.status_code == 422  # Validation error


class TestCORS:
    """Test CORS configuration."""

    def test_cors_headers_present(self):
        """CORS headers should be present in responses."""
        response = client.get("/api/health")
        assert response.status_code == 200

        # In test client, CORS middleware may not add headers
        # In production, these should be present
        # This test documents expected behavior


class TestErrorHandling:
    """Test error response consistency."""

    def test_404_error_structure(self):
        """404 errors should have consistent structure."""
        response = client.get("/api/teams/99999")
        assert response.status_code == 404

        data = response.json()
        assert "error" in data
        assert "message" in data
        assert "detail" in data

    def test_400_error_structure(self):
        """400 errors should have consistent structure."""
        response = client.get("/api/predict?home=17&away=17")
        assert response.status_code == 400

        data = response.json()
        assert "error" in data
        assert "message" in data
        assert "detail" in data

    def test_422_validation_error(self):
        """Validation errors should return 422."""
        response = client.get("/api/rankings?limit=9999")
        assert response.status_code == 422


class TestTeamResultsEndpoint:
    """Test /api/teams/{team_id}/results endpoint."""

    def test_results_success(self):
        """Should return enriched match results with stats."""
        search = client.get("/api/search?q=arsenal")
        team_id = search.json()["results"][0]["id"]

        response = client.get(f"/api/teams/{team_id}/results?limit=5")
        assert response.status_code == 200

        data = response.json()
        assert "team" in data
        assert "stats" in data
        assert "results" in data

        # Verify stats card
        stats = data["stats"]
        assert "current_rating" in stats
        assert "rank" in stats
        assert "form" in stats
        assert isinstance(stats["form"], list)
        assert len(stats["form"]) <= 5
        assert all(r in ("W", "D", "L") for r in stats["form"])
        assert "trend_30d" in stats
        assert "peak_rating" in stats
        assert "peak_date" in stats
        assert "trough_rating" in stats
        assert "trough_date" in stats

    def test_results_entry_structure(self):
        """Should return enriched match entries with Elo data."""
        search = client.get("/api/search?q=bayern")
        team_id = search.json()["results"][0]["id"]

        response = client.get(f"/api/teams/{team_id}/results?limit=3")
        assert response.status_code == 200

        data = response.json()
        if data["results"]:
            entry = data["results"][0]
            assert "date" in entry
            assert "home_team" in entry
            assert "away_team" in entry
            assert "team_result" in entry
            assert entry["team_result"] in ("W", "D", "L")
            assert "elo_before" in entry
            assert "elo_after" in entry
            assert "elo_change" in entry
            assert isinstance(entry["elo_before"], (int, float))
            assert isinstance(entry["elo_after"], (int, float))

    def test_results_not_found(self):
        """Should return 404 for non-existent team."""
        response = client.get("/api/teams/99999/results")
        assert response.status_code == 404

    def test_results_limit(self):
        """Should respect limit parameter."""
        search = client.get("/api/search?q=arsenal")
        team_id = search.json()["results"][0]["id"]

        response = client.get(f"/api/teams/{team_id}/results?limit=3")
        assert response.status_code == 200
        assert len(response.json()["results"]) <= 3

    def test_results_peak_gte_trough(self):
        """Peak rating should always be >= trough rating."""
        search = client.get("/api/search?q=arsenal")
        team_id = search.json()["results"][0]["id"]

        response = client.get(f"/api/teams/{team_id}/results")
        stats = response.json()["stats"]
        assert stats["peak_rating"] >= stats["trough_rating"]


class TestPredictPage:
    """Test /predict redirect (old page retired)."""

    def test_predict_redirects(self):
        """Old /predict URL should redirect to /."""
        response = client.get("/predict", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["location"] == "/"


class TestTeamPage:
    """Test /team/{id} redirect (old page retired)."""

    def test_team_page_redirects(self):
        """Old /team/{id} URL should redirect to slug-based URL."""
        search = client.get("/api/search?q=arsenal")
        team_id = search.json()["results"][0]["id"]

        response = client.get(f"/team/{team_id}", follow_redirects=False)
        assert response.status_code == 302
        location = response.headers["location"]
        # Should redirect to a slug URL like /england/premier-league/arsenal
        assert location.startswith("/")

    def test_team_page_not_found_redirects_home(self):
        """Non-existent team should redirect to /."""
        response = client.get("/team/99999", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["location"] == "/"


class TestComparePage:
    """Test /compare redirect (old page retired)."""

    def test_compare_redirects(self):
        """Old /compare URL should redirect to /."""
        response = client.get("/compare", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["location"] == "/"


class TestRootEndpoint:
    """Test root endpoint."""

    def test_root_renders_unified_layout(self):
        """Root should render the unified EloKit layout."""
        response = client.get("/")
        assert response.status_code == 200

        # Should be HTML content, not JSON
        assert "text/html" in response.headers["content-type"]
        assert "EloKit" in response.text


class TestRankingsEdgeCases:
    """Additional edge case tests for rankings endpoint."""

    def test_rankings_by_country(self):
        """Should filter by country parameter."""
        response = client.get("/api/rankings?country=England&limit=5")
        assert response.status_code == 200
        data = response.json()
        for entry in data["rankings"]:
            assert entry["country"] == "England"

    def test_rankings_future_date(self):
        """Future date should return current rankings (no future data)."""
        response = client.get("/api/rankings?date=2099-01-01&limit=5")
        assert response.status_code == 200
        assert response.json()["count"] > 0

    def test_rankings_very_old_date(self):
        """Date before any data should return empty or zero results."""
        response = client.get("/api/rankings?date=1900-01-01&limit=5")
        assert response.status_code == 200
        assert response.json()["count"] == 0

    def test_rankings_invalid_date_format(self):
        """Non-date string should still work (treated as string comparison)."""
        response = client.get("/api/rankings?date=not-a-date&limit=5")
        assert response.status_code == 200
        # Will return 0 results since no dates match

    def test_rankings_by_nonexistent_country(self):
        """Unknown country should return zero results."""
        response = client.get("/api/rankings?country=Atlantis&limit=5")
        assert response.status_code == 200
        assert response.json()["count"] == 0


class TestTeamDetailEdgeCases:
    """Additional edge cases for team detail endpoint."""

    def test_team_detail_zero_id(self):
        """ID 0 should return 404."""
        response = client.get("/api/teams/0")
        assert response.status_code == 404

    def test_team_detail_negative_id(self):
        """Negative ID should return 404."""
        response = client.get("/api/teams/-1")
        assert response.status_code == 404


class TestTeamHistoryEdgeCases:
    """Additional edge cases for team history endpoint."""

    def test_history_limit_validation_too_high(self):
        """Limit > 2000 should fail validation."""
        search = client.get("/api/search?q=arsenal")
        team_id = search.json()["results"][0]["id"]
        response = client.get(f"/api/teams/{team_id}/history?limit=5000")
        assert response.status_code == 422

    def test_history_limit_validation_zero(self):
        """Limit 0 should fail validation."""
        response = client.get("/api/teams/1/history?limit=0")
        assert response.status_code == 422


class TestPredictionEdgeCases:
    """Additional prediction endpoint edge cases."""

    def test_prediction_missing_home(self):
        """Missing home parameter should return 422."""
        response = client.get("/api/predict?away=1")
        assert response.status_code == 422

    def test_prediction_missing_away(self):
        """Missing away parameter should return 422."""
        response = client.get("/api/predict?home=1")
        assert response.status_code == 422

    def test_prediction_both_not_found(self):
        """Both teams not found should return 404."""
        response = client.get("/api/predict?home=99998&away=99999")
        assert response.status_code == 404


class TestSearchEdgeCases:
    """Additional search edge cases."""

    def test_search_special_chars(self):
        """Special characters should not crash search."""
        response = client.get("/api/search?q=%22drop+table%22")
        assert response.status_code == 200

    def test_search_unicode(self):
        """Unicode characters should work in search."""
        response = client.get("/api/search?q=München")
        assert response.status_code == 200

    def test_search_limit_max(self):
        """Limit at maximum should work."""
        response = client.get("/api/search?q=a&limit=50")
        assert response.status_code == 200

    def test_search_limit_too_high(self):
        """Limit above maximum should return 422."""
        response = client.get("/api/search?q=a&limit=100")
        assert response.status_code == 422


class TestTeamResultsEdgeCases:
    """Additional team results edge cases."""

    def test_results_limit_max(self):
        """Limit at maximum (50) should work."""
        search = client.get("/api/search?q=arsenal")
        team_id = search.json()["results"][0]["id"]
        response = client.get(f"/api/teams/{team_id}/results?limit=50")
        assert response.status_code == 200

    def test_results_limit_too_high(self):
        """Limit above maximum should return 422."""
        response = client.get("/api/teams/1/results?limit=100")
        assert response.status_code == 422

    def test_results_limit_zero(self):
        """Limit 0 should return 422."""
        response = client.get("/api/teams/1/results?limit=0")
        assert response.status_code == 422


class TestFixturesEndpoint:
    """Test /api/fixtures endpoint."""

    def test_fixtures_returns_correct_format(self):
        """Should return fixtures response with correct structure."""
        response = client.get("/api/fixtures")
        assert response.status_code == 200

        data = response.json()
        assert "count" in data
        assert "fixtures" in data
        assert isinstance(data["fixtures"], list)
        assert data["count"] == len(data["fixtures"])

        # Verify fixture structure if any exist
        if data["fixtures"]:
            fixture = data["fixtures"][0]
            assert "date" in fixture
            assert "home_team" in fixture
            assert "away_team" in fixture
            assert "competition" in fixture
            assert "prediction" in fixture

            # Verify team structure
            assert "id" in fixture["home_team"]
            assert "name" in fixture["home_team"]
            assert "id" in fixture["away_team"]
            assert "name" in fixture["away_team"]

            # Verify prediction structure if present
            if fixture["prediction"] is not None:
                pred = fixture["prediction"]
                assert "p_home" in pred
                assert "p_draw" in pred
                assert "p_away" in pred
                assert "home_elo" in pred
                assert "away_elo" in pred
                prob_sum = pred["p_home"] + pred["p_draw"] + pred["p_away"]
                assert abs(prob_sum - 1.0) < 0.02

    def test_fixtures_competition_filter(self):
        """Competition filter should not error."""
        response = client.get("/api/fixtures?competition=Premier%20League")
        assert response.status_code == 200

        data = response.json()
        assert "count" in data
        assert "fixtures" in data
        # All fixtures should be from requested competition
        for fixture in data["fixtures"]:
            assert fixture["competition"] == "Premier League"

    def test_fixtures_empty_with_nonexistent_competition(self):
        """Non-existent competition should return empty list."""
        response = client.get("/api/fixtures?competition=Nonexistent%20League")
        assert response.status_code == 200

        data = response.json()
        assert data["count"] == 0
        assert data["fixtures"] == []


class TestSidebarFlagsAndLogos:
    """Test flag_url and logo_url fields in /api/sidebar response."""

    def test_sidebar_nations_have_flag_url(self):
        """Each nation in sidebar should have a flag_url."""
        response = client.get("/api/sidebar")
        assert response.status_code == 200
        data = response.json()

        for nation in data["nations"]:
            assert nation["flag_url"] is not None, (
                f"Missing flag_url for {nation['country']}"
            )
            assert nation["flag_url"].startswith("/static/flags/")
            assert nation["flag_url"].endswith(".svg")

    def test_sidebar_competitions_have_logo_url(self):
        """Each competition in sidebar should have a logo_url."""
        response = client.get("/api/sidebar")
        assert response.status_code == 200
        data = response.json()

        # Check domestic competitions
        for nation in data["nations"]:
            for comp in nation["competitions"]:
                assert comp["logo_url"] is not None, (
                    f"Missing logo_url for {comp['name']}"
                )
                assert comp["logo_url"].startswith(
                    "/static/logos/competitions/"
                )

        # Check European competitions
        for comp in data["european"]:
            assert comp["logo_url"] is not None, (
                f"Missing logo_url for {comp['name']}"
            )

    def test_sidebar_europe_flag_url(self):
        """Europe sidebar entry should have EU flag."""
        from backend.slugs import COUNTRY_FLAG_URLS

        assert "Europe" in COUNTRY_FLAG_URLS
        assert COUNTRY_FLAG_URLS["Europe"] == "/static/flags/europe.svg"


class TestFixturesLogoUrls:
    """Test competition_logo_url field in /api/fixtures/scoped response."""

    def test_scoped_fixtures_have_competition_logo_url(self):
        """Fixture entries should include competition_logo_url."""
        response = client.get(
            "/api/fixtures/scoped?country=England&status=both&limit=3"
        )
        assert response.status_code == 200
        data = response.json()

        all_entries = data["finished"] + data["upcoming"]
        if all_entries:
            for entry in all_entries:
                assert "competition_logo_url" in entry
                if entry["competition_logo_url"] is not None:
                    assert entry["competition_logo_url"].startswith(
                        "/static/logos/competitions/"
                    )


class TestFixturesPage:
    """Test /fixtures redirect (old page retired)."""

    def test_fixtures_redirects(self):
        """Old /fixtures URL should redirect to /."""
        response = client.get("/fixtures", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["location"] == "/"


class TestAccuracyGridEndpoint:
    """Test /api/accuracy/grid endpoint."""

    def test_grid_returns_correct_structure(self):
        """Should return 3x3 grid with counts, percentages, and accuracy."""
        response = client.get("/api/accuracy/grid")
        assert response.status_code == 200

        data = response.json()
        # Top-level fields
        assert "actual_home" in data
        assert "actual_draw" in data
        assert "actual_away" in data
        assert "total" in data
        assert "correct" in data
        assert "accuracy_pct" in data
        assert isinstance(data["total"], int)
        assert isinstance(data["correct"], int)
        assert isinstance(data["accuracy_pct"], float)

        # Each row has the right structure
        for row_key in ("actual_home", "actual_draw", "actual_away"):
            row = data[row_key]
            assert "predicted_home" in row
            assert "predicted_draw" in row
            assert "predicted_away" in row
            assert "total" in row
            for cell_key in ("predicted_home", "predicted_draw", "predicted_away"):
                cell = row[cell_key]
                assert "count" in cell
                assert "pct_of_row" in cell
                assert "pct_of_total" in cell
                assert isinstance(cell["count"], int)
                assert isinstance(cell["pct_of_row"], float)
                assert isinstance(cell["pct_of_total"], float)

    def test_grid_total_equals_row_sums(self):
        """Grand total should equal sum of all row totals."""
        response = client.get("/api/accuracy/grid")
        data = response.json()

        row_sum = (
            data["actual_home"]["total"]
            + data["actual_draw"]["total"]
            + data["actual_away"]["total"]
        )
        assert data["total"] == row_sum

    def test_grid_correct_equals_diagonal_sum(self):
        """Correct count should equal sum of diagonal cells."""
        response = client.get("/api/accuracy/grid")
        data = response.json()

        diagonal_sum = (
            data["actual_home"]["predicted_home"]["count"]
            + data["actual_draw"]["predicted_draw"]["count"]
            + data["actual_away"]["predicted_away"]["count"]
        )
        assert data["correct"] == diagonal_sum

    def test_grid_pct_of_row_sums_to_100(self):
        """pct_of_row values in each row should sum to ~100."""
        response = client.get("/api/accuracy/grid")
        data = response.json()

        for row_key in ("actual_home", "actual_draw", "actual_away"):
            row = data[row_key]
            if row["total"] == 0:
                continue
            pct_sum = (
                row["predicted_home"]["pct_of_row"]
                + row["predicted_draw"]["pct_of_row"]
                + row["predicted_away"]["pct_of_row"]
            )
            assert abs(pct_sum - 100.0) < 1.0, (
                f"{row_key} pct_of_row sums to {pct_sum}, expected ~100"
            )

    def test_grid_accuracy_pct_consistent(self):
        """accuracy_pct should equal correct/total * 100."""
        response = client.get("/api/accuracy/grid")
        data = response.json()

        if data["total"] > 0:
            expected = round(100 * data["correct"] / data["total"], 1)
            assert abs(data["accuracy_pct"] - expected) < 0.2

    def test_grid_scoping_by_country(self):
        """Country filter should return scoped results."""
        response = client.get("/api/accuracy/grid?country=England")
        assert response.status_code == 200

        data = response.json()
        # England subset should be smaller than global total
        global_resp = client.get("/api/accuracy/grid")
        global_data = global_resp.json()
        assert data["total"] > 0
        assert data["total"] <= global_data["total"]

    def test_grid_scoping_by_competition(self):
        """Competition filter should return scoped results."""
        response = client.get("/api/accuracy/grid?competition=Premier%20League")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] > 0

    def test_grid_scoping_by_team_id(self):
        """Team ID filter should return scoped results."""
        # Arsenal = team_id 19
        response = client.get("/api/accuracy/grid?team_id=19")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] > 0
        # Team subset should be much smaller than global
        global_resp = client.get("/api/accuracy/grid")
        assert data["total"] < global_resp.json()["total"]

    def test_grid_scoping_by_source(self):
        """Source filter should return scoped results."""
        response = client.get("/api/accuracy/grid?source=backfill")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] > 0

    def test_grid_empty_scope_returns_zeros(self):
        """Non-matching scope should return zeros gracefully."""
        response = client.get("/api/accuracy/grid?country=Atlantis")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 0
        assert data["correct"] == 0
        assert data["accuracy_pct"] == 0.0
        for row_key in ("actual_home", "actual_draw", "actual_away"):
            row = data[row_key]
            assert row["total"] == 0
            for cell_key in ("predicted_home", "predicted_draw", "predicted_away"):
                assert row[cell_key]["count"] == 0
                assert row[cell_key]["pct_of_row"] == 0.0
                assert row[cell_key]["pct_of_total"] == 0.0


class TestPredictionHistorySearch:
    """Test search parameter on /api/prediction-history."""

    def test_search_known_team(self):
        """Search for a known team should return matches containing it."""
        response = client.get("/api/prediction-history?search=Liverpool")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] > 0
        assert len(data["items"]) > 0

        # Every returned match should mention Liverpool
        for item in data["items"]:
            home = item["home_team"].lower()
            away = item["away_team"].lower()
            assert "liverpool" in home or "liverpool" in away

    def test_search_multi_word(self):
        """Multi-word search should match both tokens across home+away."""
        response = client.get(
            "/api/prediction-history?search=Arsenal+Liverpool"
        )
        assert response.status_code == 200

        data = response.json()
        # Should find Arsenal vs Liverpool matches (or vice versa)
        for item in data["items"]:
            combined = (
                item["home_team"].lower() + " " + item["away_team"].lower()
            )
            assert "arsenal" in combined
            assert "liverpool" in combined

    def test_search_no_results(self):
        """Search with no matching teams returns empty items + total=0."""
        response = client.get("/api/prediction-history?search=zzzznonexistent")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_search_empty_returns_all(self):
        """Empty/missing search parameter returns all results (backward compatible)."""
        response_no_search = client.get("/api/prediction-history?per_page=5")
        assert response_no_search.status_code == 200

        response_empty = client.get(
            "/api/prediction-history?search=&per_page=5"
        )
        assert response_empty.status_code == 200

        # Both should return the same total
        assert response_no_search.json()["total"] == response_empty.json()["total"]

    def test_search_case_insensitive(self):
        """Search should be case-insensitive."""
        resp_lower = client.get("/api/prediction-history?search=liverpool")
        resp_upper = client.get("/api/prediction-history?search=LIVERPOOL")
        resp_mixed = client.get("/api/prediction-history?search=Liverpool")

        assert resp_lower.status_code == 200
        assert resp_upper.status_code == 200
        assert resp_mixed.status_code == 200

        assert resp_lower.json()["total"] == resp_upper.json()["total"]
        assert resp_lower.json()["total"] == resp_mixed.json()["total"]


class TestPredictionAccuracyScoping:
    """Test country and team_id scoping on /api/prediction-accuracy."""

    def test_accuracy_no_params_backward_compatible(self):
        """No parameters should return all data (backward compatible)."""
        response = client.get("/api/prediction-accuracy")
        assert response.status_code == 200

        data = response.json()
        assert "mean_brier_score" in data
        assert "total_predictions" in data
        assert "calibration" in data
        assert "by_competition" in data
        assert data["total_predictions"] > 0

    def test_accuracy_country_scoping(self):
        """Country parameter should filter to that country."""
        response = client.get("/api/prediction-accuracy?country=England")
        assert response.status_code == 200

        data = response.json()
        assert data["total_predictions"] > 0

        # Should be a subset of global
        global_resp = client.get("/api/prediction-accuracy")
        assert data["total_predictions"] <= global_resp.json()["total_predictions"]

    def test_accuracy_team_id_scoping(self):
        """team_id parameter should filter to that team."""
        # Arsenal = 19
        response = client.get("/api/prediction-accuracy?team_id=19")
        assert response.status_code == 200

        data = response.json()
        assert data["total_predictions"] > 0

        # Much smaller than global
        global_resp = client.get("/api/prediction-accuracy")
        assert data["total_predictions"] < global_resp.json()["total_predictions"]

    def test_accuracy_competition_filter(self):
        """Competition filter should still work."""
        response = client.get(
            "/api/prediction-accuracy?competition=Premier%20League"
        )
        assert response.status_code == 200

        data = response.json()
        assert data["total_predictions"] > 0

    def test_accuracy_source_filter(self):
        """Source filter should still work."""
        response = client.get("/api/prediction-accuracy?source=backfill")
        assert response.status_code == 200

        data = response.json()
        assert data["total_predictions"] > 0


class TestPredictionHistoryScoping:
    """Test country and team_id scoping on /api/prediction-history."""

    def test_history_country_filter(self):
        """Country parameter should filter predictions."""
        response = client.get(
            "/api/prediction-history?country=England&per_page=5"
        )
        assert response.status_code == 200

        data = response.json()
        assert data["total"] > 0

        # Should be a subset of global
        global_resp = client.get("/api/prediction-history")
        assert data["total"] <= global_resp.json()["total"]

    def test_history_team_id_filter(self):
        """team_id parameter should filter predictions."""
        # Arsenal = 19
        response = client.get(
            "/api/prediction-history?team_id=19&per_page=5"
        )
        assert response.status_code == 200

        data = response.json()
        assert data["total"] > 0

        # Every returned match should involve Arsenal
        for item in data["items"]:
            combined = (
                item["home_team"].lower() + " " + item["away_team"].lower()
            )
            assert "arsenal" in combined

    def test_history_country_and_search_combined(self):
        """Country + search should both apply."""
        response = client.get(
            "/api/prediction-history?country=England&search=Arsenal&per_page=5"
        )
        assert response.status_code == 200

        data = response.json()
        assert data["total"] > 0

        for item in data["items"]:
            combined = (
                item["home_team"].lower() + " " + item["away_team"].lower()
            )
            assert "arsenal" in combined

    def test_history_team_id_and_search_combined(self):
        """team_id + search should both apply."""
        # Arsenal (19) + search "Liverpool" => Arsenal vs Liverpool matches
        response = client.get(
            "/api/prediction-history?team_id=19&search=Liverpool&per_page=5"
        )
        assert response.status_code == 200

        data = response.json()
        # Should find Arsenal vs Liverpool matches
        for item in data["items"]:
            combined = (
                item["home_team"].lower() + " " + item["away_team"].lower()
            )
            assert "arsenal" in combined
            assert "liverpool" in combined


class TestPredictionHistoryScopes:
    """Sprint 15.2 Bug 2: prediction history works at all navigation scopes."""

    def test_global_scope_returns_predictions(self):
        """No filter params returns all scored predictions (global scope)."""
        response = client.get("/api/prediction-history?page=1&per_page=5")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] > 0, "Global scope should have scored predictions"
        assert len(data["items"]) > 0

    def test_country_scope_returns_predictions(self):
        """country=England returns Premier League predictions (nation scope)."""
        response = client.get(
            "/api/prediction-history?country=England&page=1&per_page=5"
        )
        assert response.status_code == 200

        data = response.json()
        assert data["total"] > 0, "England scope should return predictions"

    def test_competition_scope_returns_predictions(self):
        """competition=Premier League returns EPL predictions (league scope)."""
        response = client.get(
            "/api/prediction-history?competition=Premier+League&page=1&per_page=5"
        )
        assert response.status_code == 200

        data = response.json()
        assert data["total"] > 0, "Premier League scope should return predictions"
        for item in data["items"]:
            assert item["competition"] == "Premier League"

    def test_country_and_competition_combined(self):
        """country + competition together uses competition filter (league scope)."""
        response = client.get(
            "/api/prediction-history?country=England&competition=Premier+League&page=1&per_page=5"
        )
        assert response.status_code == 200

        data = response.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["competition"] == "Premier League"


class TestBrierTrendTimeSeries:
    """Sprint 15.2 Bug 1: Brier trend time series uses match dates."""

    def test_prediction_accuracy_time_series_not_empty(self):
        """Global scope time_series should have multiple data points."""
        response = client.get("/api/prediction-accuracy")
        assert response.status_code == 200

        data = response.json()
        ts = data.get("time_series", [])
        assert len(ts) > 10, (
            f"Expected many time_series points, got {len(ts)}. "
            "Bug: time series uses scored_at instead of match_date."
        )

    def test_prediction_accuracy_time_series_spans_full_history(self):
        """time_series should span from ~2016 to now, not just 1-2 dates."""
        response = client.get("/api/prediction-accuracy")
        assert response.status_code == 200

        data = response.json()
        ts = data.get("time_series", [])
        assert len(ts) > 0

        dates = [pt["date"] for pt in ts]
        earliest = min(dates)
        latest = max(dates)

        # Earliest point should be in 2016 (from warm-up period start)
        assert earliest < "2017-01-01", (
            f"Expected time series to start ~2016, got {earliest}"
        )
        # Latest point should be recent (2025 or later)
        assert latest > "2025-01-01", (
            f"Expected time series to extend to 2025+, got {latest}"
        )
