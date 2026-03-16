"""Tests for match prediction module."""

import pytest

from src.prediction import predict_match, predict_probs


class TestPredictProbs:
    def test_equal_teams(self):
        """Equal expected score should give ~34% draw probability."""
        p_h, p_d, p_a = predict_probs(0.5)
        assert abs(p_h - p_a) < 0.001
        assert abs(p_d - 0.34) < 0.01
        assert abs(p_h + p_d + p_a - 1.0) < 0.001

    def test_strong_home_favorite(self):
        """Strong home favorite: high p_home, low p_away."""
        p_h, p_d, p_a = predict_probs(0.8)
        assert p_h > p_a
        assert p_h > p_d
        assert abs(p_h + p_d + p_a - 1.0) < 0.001

    def test_away_favorite(self):
        """Away team favored when e_home < 0.5."""
        p_h, p_d, p_a = predict_probs(0.3)
        assert p_a > p_h
        assert abs(p_h + p_d + p_a - 1.0) < 0.001

    def test_draw_minimum(self):
        """Draw probability should not go below 5%."""
        p_h, p_d, p_a = predict_probs(0.99)
        assert p_d >= 0.05
        assert abs(p_h + p_d + p_a - 1.0) < 0.001

    def test_probabilities_sum_to_one(self):
        """Probabilities must sum to 1 for any input."""
        for e_home in [0.1, 0.3, 0.5, 0.7, 0.9]:
            p_h, p_d, p_a = predict_probs(e_home)
            assert abs(p_h + p_d + p_a - 1.0) < 0.001


class TestPredictMatch:
    @pytest.fixture
    def sample_ratings(self):
        return {
            "Arsenal": 1550.0,
            "Chelsea": 1480.0,
            "Bayern Munich": 1700.0,
            "Burnley": 1350.0,
        }

    def test_basic_prediction(self, sample_ratings):
        result = predict_match("Arsenal", "Chelsea", sample_ratings)
        assert result["home_team"] == "Arsenal"
        assert result["away_team"] == "Chelsea"
        assert result["home_rating"] == 1550.0
        assert result["away_rating"] == 1480.0
        assert abs(result["p_home"] + result["p_draw"] + result["p_away"] - 1.0) < 0.01

    def test_home_advantage(self, sample_ratings):
        """Home team should be favored when ratings are equal."""
        ratings = {"Team A": 1500.0, "Team B": 1500.0}
        result = predict_match("Team A", "Team B", ratings)
        assert result["p_home"] > result["p_away"]

    def test_strong_favorite(self, sample_ratings):
        result = predict_match("Bayern Munich", "Burnley", sample_ratings)
        assert result["p_home"] > 0.7  # Bayern at home should be heavy favorite
        assert result["p_away"] < 0.1

    def test_rating_diff(self, sample_ratings):
        result = predict_match("Arsenal", "Chelsea", sample_ratings)
        assert result["rating_diff"] == 70.0

    def test_unknown_team_raises(self, sample_ratings):
        with pytest.raises(KeyError, match="Team not found"):
            predict_match("Arsenal", "Nonexistent FC", sample_ratings)

    def test_away_can_be_favored(self, sample_ratings):
        """Even with home advantage, a much stronger away team can be favored."""
        result = predict_match("Burnley", "Bayern Munich", sample_ratings)
        assert result["p_away"] > result["p_home"]

    def test_custom_settings(self, sample_ratings):
        """Prediction with custom settings should work."""
        from src.config import EloSettings
        settings = EloSettings(home_advantage=0.0)
        result = predict_match("Arsenal", "Chelsea", sample_ratings, settings=settings)
        assert abs(result["p_home"] + result["p_draw"] + result["p_away"] - 1.0) < 0.01

    def test_identical_ratings(self):
        """Equal-rated teams with home advantage."""
        ratings = {"A": 1500.0, "B": 1500.0}
        result = predict_match("A", "B", ratings)
        assert result["rating_diff"] == 0.0
        assert result["p_home"] > result["p_away"]  # home advantage


class TestPredictProbsEdgeCases:
    """Edge cases for predict_probs."""

    def test_e_home_zero(self):
        """e_home=0 should give all probability to away."""
        p_h, p_d, p_a = predict_probs(0.0)
        assert p_h == pytest.approx(0.0, abs=0.01)
        assert p_a > 0.5
        assert abs(p_h + p_d + p_a - 1.0) < 0.001

    def test_e_home_one(self):
        """e_home=1 should give all probability to home."""
        p_h, p_d, p_a = predict_probs(1.0)
        assert p_a == pytest.approx(0.0, abs=0.01)
        assert p_h > 0.5
        assert abs(p_h + p_d + p_a - 1.0) < 0.001

    def test_draw_never_negative(self):
        """Draw probability should never be negative."""
        for e in [0.0, 0.1, 0.5, 0.9, 1.0]:
            _, p_d, _ = predict_probs(e)
            assert p_d >= 0

    def test_all_probs_non_negative(self):
        """All probabilities should be non-negative."""
        for e in [0.0, 0.01, 0.5, 0.99, 1.0]:
            p_h, p_d, p_a = predict_probs(e)
            assert p_h >= 0
            assert p_d >= 0
            assert p_a >= 0
