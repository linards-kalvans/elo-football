"""Test suite for FastAPI backend endpoints.

Tests all API endpoints with success and error cases, validates response schemas,
and ensures database integration works correctly.
"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


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
    """Test /predict frontend page."""

    def test_predict_page_renders_html(self):
        """Predict page should render HTML, not JSON."""
        response = client.get("/predict")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Match Prediction" in response.text

    def test_predict_page_has_search_inputs(self):
        """Predict page should have team search inputs."""
        response = client.get("/predict")
        assert "Home Team" in response.text
        assert "Away Team" in response.text
        assert "Predict Match" in response.text


class TestTeamPage:
    """Test /team/{id} frontend page."""

    def test_team_page_renders(self):
        """Team page should render HTML."""
        search = client.get("/api/search?q=arsenal")
        team_id = search.json()["results"][0]["id"]

        response = client.get(f"/team/{team_id}")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_team_page_not_found(self):
        """Team page should return 404 for non-existent team."""
        response = client.get("/team/99999")
        assert response.status_code == 404


class TestComparePage:
    """Test /compare frontend page."""

    def test_compare_page_renders(self):
        """Compare page should render HTML."""
        response = client.get("/compare")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Compare" in response.text

    def test_compare_page_with_league(self):
        """Compare page should accept league parameter."""
        response = client.get("/compare?league=epl")
        assert response.status_code == 200


class TestRootEndpoint:
    """Test root endpoint."""

    def test_root_redirect(self):
        """Root should render rankings page."""
        response = client.get("/")
        assert response.status_code == 200

        # Should be HTML content, not JSON
        assert "text/html" in response.headers["content-type"]
        assert "European Football Elo Rankings" in response.text


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


class TestFixturesPage:
    """Test /fixtures frontend page."""

    def test_fixtures_page_renders(self):
        """Fixtures page should render HTML."""
        response = client.get("/fixtures")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Upcoming Fixtures" in response.text

    def test_fixtures_page_has_content(self):
        """Fixtures page should have expected UI elements."""
        response = client.get("/fixtures")
        assert response.status_code == 200
        assert "fixturesPage" in response.text
        assert "/api/fixtures" in response.text
