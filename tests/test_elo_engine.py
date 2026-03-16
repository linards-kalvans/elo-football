"""Comprehensive tests for the Elo rating engine."""

import math

import pandas as pd
import pytest

from src.config import EloSettings
from src.elo_engine import EloEngine, EloResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def default_settings() -> EloSettings:
    """Default settings (no .env interference)."""
    return EloSettings(
        k_factor=30.0,
        initial_elo=1500.0,
        home_advantage=65.0,
        decay_rate=0.95,
        promoted_elo=1350.0,
        spread=500.0,
        mov_autocorr_coeff=2.2,
        mov_autocorr_scale=0.001,
    )


@pytest.fixture
def engine(default_settings: EloSettings) -> EloEngine:
    return EloEngine(default_settings)


@pytest.fixture
def simple_matches() -> pd.DataFrame:
    """Three-match synthetic dataset within a single season."""
    return pd.DataFrame({
        "Date": pd.to_datetime(["2024-08-10", "2024-08-17", "2024-08-24"]),
        "HomeTeam": ["TeamA", "TeamB", "TeamA"],
        "AwayTeam": ["TeamB", "TeamC", "TeamC"],
        "FTHG": [2, 1, 3],
        "FTAG": [1, 1, 0],
        "FTR": ["H", "D", "H"],
        "Season": ["2425", "2425", "2425"],
    })


@pytest.fixture
def multi_season_matches() -> pd.DataFrame:
    """Matches spanning two seasons with a promoted team in season 2."""
    return pd.DataFrame({
        "Date": pd.to_datetime([
            "2023-08-10", "2023-08-17",
            "2024-08-10", "2024-08-17",
        ]),
        "HomeTeam": ["TeamA", "TeamB", "TeamA", "NewTeam"],
        "AwayTeam": ["TeamB", "TeamA", "NewTeam", "TeamB"],
        "FTHG": [1, 0, 2, 0],
        "FTAG": [0, 1, 0, 3],
        "FTR": ["H", "A", "H", "A"],
        "Season": ["2324", "2324", "2425", "2425"],
    })


# ---------------------------------------------------------------------------
# expected_score tests
# ---------------------------------------------------------------------------
class TestExpectedScore:
    def test_equal_ratings_gives_50_percent(self, engine: EloEngine) -> None:
        assert engine.expected_score(1500, 1500) == pytest.approx(0.5)

    def test_symmetry(self, engine: EloEngine) -> None:
        """P(A beats B) + P(B beats A) = 1."""
        ea = engine.expected_score(1600, 1400)
        eb = engine.expected_score(1400, 1600)
        assert ea + eb == pytest.approx(1.0)

    def test_higher_rating_favored(self, engine: EloEngine) -> None:
        assert engine.expected_score(1600, 1400) > 0.5

    def test_large_gap(self, engine: EloEngine) -> None:
        """Very large rating gap should give near-certainty."""
        assert engine.expected_score(2000, 1000) > 0.99

    def test_spread_sensitivity(self) -> None:
        """Wider spread → less confident predictions."""
        narrow = EloEngine(EloSettings(spread=400.0))
        wide = EloEngine(EloSettings(spread=600.0))
        # For same rating gap, narrow spread gives more extreme probability
        p_narrow = narrow.expected_score(1600, 1400)
        p_wide = wide.expected_score(1600, 1400)
        assert p_narrow > p_wide


# ---------------------------------------------------------------------------
# mov_multiplier tests
# ---------------------------------------------------------------------------
class TestMoVMultiplier:
    def test_one_goal_diff(self, engine: EloEngine) -> None:
        """1-goal win: normalized to multiplier of exactly 1.0."""
        mult = engine.mov_multiplier(goal_diff=1, elo_diff=0)
        # With elo_diff=0, autocorr = coeff / coeff = 1.0
        assert mult == pytest.approx(1.0)

    def test_zero_goal_diff(self, engine: EloEngine) -> None:
        """0 goal diff (draw): ln(1) = 0 → multiplier is 0."""
        assert engine.mov_multiplier(goal_diff=0, elo_diff=0) == pytest.approx(0.0)

    def test_larger_diff_higher_multiplier(self, engine: EloEngine) -> None:
        """More goals → higher multiplier."""
        m1 = engine.mov_multiplier(1, 0)
        m3 = engine.mov_multiplier(3, 0)
        assert m3 > m1

    def test_autocorrelation_reduces_for_favorites(self, engine: EloEngine) -> None:
        """When the winner has much higher Elo, autocorr correction reduces K."""
        m_upset = engine.mov_multiplier(2, elo_diff=-200)  # underdog wins
        m_expected = engine.mov_multiplier(2, elo_diff=200)  # favorite wins
        assert m_upset > m_expected

    def test_autocorrelation_neutral(self, engine: EloEngine) -> None:
        """Equal teams: autocorr correction = 1.0."""
        mult = engine.mov_multiplier(2, elo_diff=0)
        assert mult == pytest.approx(math.log(3) / math.log(2))


# ---------------------------------------------------------------------------
# elo_update tests
# ---------------------------------------------------------------------------
class TestEloUpdate:
    def test_home_win(self, engine: EloEngine) -> None:
        new_h, new_a, dh, da = engine.elo_update(1500, 1500, "H", 2, 0)
        assert dh > 0
        assert da < 0
        assert dh == pytest.approx(-da, abs=0.01)

    def test_away_win(self, engine: EloEngine) -> None:
        new_h, new_a, dh, da = engine.elo_update(1500, 1500, "A", 0, 1)
        assert dh < 0
        assert da > 0

    def test_draw(self, engine: EloEngine) -> None:
        """Draw between equal teams with home advantage → home loses a tiny bit."""
        _, _, dh, da = engine.elo_update(1500, 1500, "D", 0, 0)
        # Home is expected to win more, so draw is slightly bad for home
        assert dh < 0
        assert da > 0

    def test_draw_zero_goals_uses_base_k(self, engine: EloEngine) -> None:
        """0-0 draw: goal_diff=0, MoV not applied → base K used.

        Home team is still slightly penalized because home advantage
        makes e_home > 0.5, so a draw is a slight underperformance.
        """
        _, _, dh, da = engine.elo_update(1500, 1500, "D", 0, 0)
        # Home expected to win more → draw is bad for home
        assert dh < 0
        assert da > 0

    def test_home_advantage_effect(self) -> None:
        """Home team should be expected to win more with higher home advantage."""
        low_ha = EloEngine(EloSettings(home_advantage=0.0))
        high_ha = EloEngine(EloSettings(home_advantage=100.0))
        # Home win with equal teams — smaller delta with higher HA (less surprising)
        _, _, dh_low, _ = low_ha.elo_update(1500, 1500, "H", 1, 0)
        _, _, dh_high, _ = high_ha.elo_update(1500, 1500, "H", 1, 0)
        assert dh_low > dh_high  # Less expected → bigger reward

    def test_mov_scales_update(self, engine: EloEngine) -> None:
        """Bigger win → larger rating change."""
        _, _, dh_1, _ = engine.elo_update(1500, 1500, "H", 1, 0)
        _, _, dh_4, _ = engine.elo_update(1500, 1500, "H", 4, 0)
        assert abs(dh_4) > abs(dh_1)

    def test_ratings_sum_preserved(self, engine: EloEngine) -> None:
        """Total Elo in the system is conserved per match."""
        r_h, r_a = 1600, 1400
        new_h, new_a, _, _ = engine.elo_update(r_h, r_a, "H", 2, 1)
        assert (new_h + new_a) == pytest.approx(r_h + r_a, abs=0.01)


# ---------------------------------------------------------------------------
# apply_time_decay tests
# ---------------------------------------------------------------------------
class TestTimeDecay:
    def test_no_decay_same_day(self, engine: EloEngine) -> None:
        ratings = {"TeamA": 1600.0}
        last = {"TeamA": pd.Timestamp("2024-01-01")}
        engine.apply_time_decay("TeamA", pd.Timestamp("2024-01-01"), ratings, last)
        assert ratings["TeamA"] == 1600.0

    def test_decay_toward_initial(self, engine: EloEngine) -> None:
        """After a long gap, rating should regress toward initial_elo."""
        ratings = {"TeamA": 1700.0}
        last = {"TeamA": pd.Timestamp("2023-01-01")}
        engine.apply_time_decay("TeamA", pd.Timestamp("2024-01-01"), ratings, last)
        assert 1500 < ratings["TeamA"] < 1700

    def test_decay_rate_1_no_decay(self) -> None:
        """decay_rate=1.0 means no decay at all."""
        engine = EloEngine(EloSettings(decay_rate=1.0))
        ratings = {"TeamA": 1700.0}
        last = {"TeamA": pd.Timestamp("2020-01-01")}
        engine.apply_time_decay("TeamA", pd.Timestamp("2024-01-01"), ratings, last)
        assert ratings["TeamA"] == pytest.approx(1700.0)

    def test_new_team_no_crash(self, engine: EloEngine) -> None:
        """Team not in last_match dict → no-op."""
        ratings = {"TeamA": 1500.0}
        engine.apply_time_decay("TeamA", pd.Timestamp("2024-01-01"), ratings, {})
        assert ratings["TeamA"] == 1500.0

    def test_longer_gap_more_decay(self, engine: EloEngine) -> None:
        ratings_short = {"TeamA": 1700.0}
        ratings_long = {"TeamA": 1700.0}
        last = {"TeamA": pd.Timestamp("2023-06-01")}
        engine.apply_time_decay("TeamA", pd.Timestamp("2023-09-01"), ratings_short, last)
        engine.apply_time_decay("TeamA", pd.Timestamp("2025-06-01"), ratings_long, last)
        # Longer gap → more decay → closer to 1500
        assert ratings_long["TeamA"] < ratings_short["TeamA"]


# ---------------------------------------------------------------------------
# compute_ratings integration tests
# ---------------------------------------------------------------------------
class TestComputeRatings:
    def test_basic_output_shape(self, engine: EloEngine, simple_matches: pd.DataFrame) -> None:
        result = engine.compute_ratings(simple_matches)
        assert isinstance(result, EloResult)
        assert result.matches_processed == 3
        assert len(result.deltas) == 3
        assert len(result.ratings) == 3  # TeamA, TeamB, TeamC

    def test_all_teams_have_history(self, engine: EloEngine, simple_matches: pd.DataFrame) -> None:
        result = engine.compute_ratings(simple_matches)
        for team in ["TeamA", "TeamB", "TeamC"]:
            assert team in result.history
            assert len(result.history[team]) >= 2  # init + at least 1 match

    def test_promoted_team_lower_start(self, engine: EloEngine, multi_season_matches: pd.DataFrame) -> None:
        """Teams appearing after the first season start at promoted_elo."""
        result = engine.compute_ratings(multi_season_matches)
        # NewTeam first appears in season 2425 → should start at 1350
        first_rating = result.history["NewTeam"][0][1]
        assert first_rating == engine.settings.promoted_elo

    def test_first_season_teams_start_at_initial(self, engine: EloEngine, multi_season_matches: pd.DataFrame) -> None:
        result = engine.compute_ratings(multi_season_matches)
        assert result.history["TeamA"][0][1] == engine.settings.initial_elo
        assert result.history["TeamB"][0][1] == engine.settings.initial_elo

    def test_winner_gains_rating(self, engine: EloEngine, simple_matches: pd.DataFrame) -> None:
        """TeamA wins twice (match 1 and 3) → should end higher than start."""
        result = engine.compute_ratings(simple_matches)
        assert result.ratings["TeamA"] > engine.settings.initial_elo

    def test_ratings_conservation(self, engine: EloEngine, simple_matches: pd.DataFrame) -> None:
        """Total Elo across all teams should remain near N * initial_elo.

        With time decay, there can be small deviations, but the system
        should not wildly inflate or deflate.
        """
        result = engine.compute_ratings(simple_matches)
        total = sum(result.ratings.values())
        expected_total = len(result.ratings) * engine.settings.initial_elo
        # Allow 5% tolerance due to time decay
        assert abs(total - expected_total) / expected_total < 0.05


# ---------------------------------------------------------------------------
# get_rankings tests
# ---------------------------------------------------------------------------
class TestGetRankings:
    def test_sorted_descending(self, engine: EloEngine) -> None:
        ratings = {"A": 1400, "B": 1600, "C": 1500}
        rankings = engine.get_rankings(ratings)
        assert [team for team, _ in rankings] == ["B", "C", "A"]

    def test_all_teams_included(self, engine: EloEngine) -> None:
        ratings = {"X": 1500, "Y": 1500}
        assert len(engine.get_rankings(ratings)) == 2


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------
class TestEdgeCases:
    def test_single_match(self, engine: EloEngine) -> None:
        matches = pd.DataFrame({
            "Date": pd.to_datetime(["2024-01-01"]),
            "HomeTeam": ["A"],
            "AwayTeam": ["B"],
            "FTHG": [1],
            "FTAG": [0],
            "FTR": ["H"],
            "Season": ["2425"],
        })
        result = engine.compute_ratings(matches)
        assert result.matches_processed == 1
        assert result.ratings["A"] > result.ratings["B"]

    def test_high_scoring_draw(self, engine: EloEngine) -> None:
        """5-5 draw: goal_diff=0, base K used (same as 0-0 draw)."""
        _, _, dh_55, _ = engine.elo_update(1500, 1500, "D", 5, 5)
        _, _, dh_00, _ = engine.elo_update(1500, 1500, "D", 0, 0)
        # Both draws have goal_diff=0 → same K → same delta
        assert dh_55 == pytest.approx(dh_00)

    def test_extreme_rating_gap(self, engine: EloEngine) -> None:
        """2000 vs 1000 — should not produce NaN or inf."""
        new_h, new_a, dh, da = engine.elo_update(2000, 1000, "H", 3, 0)
        assert math.isfinite(new_h)
        assert math.isfinite(new_a)
        assert math.isfinite(dh)

    def test_custom_settings(self) -> None:
        """Engine respects non-default settings."""
        settings = EloSettings(k_factor=50.0, spread=400.0, home_advantage=0.0)
        engine = EloEngine(settings)
        _, _, dh, _ = engine.elo_update(1500, 1500, "H", 1, 0)
        # K=50, no home advantage, 1-goal diff → predictable delta
        expected_k_adj = 50 * 1.0 * 1.0  # log(2)/log(2)=1.0, autocorr=1 at elo_diff=0
        expected_delta = expected_k_adj * (1.0 - 0.5)  # s_home=1, e_home=0.5
        assert dh == pytest.approx(expected_delta)


# ---------------------------------------------------------------------------
# get_ratings_at tests
# ---------------------------------------------------------------------------
class TestGetRatingsAt:
    def test_exact_date(self, engine: EloEngine, simple_matches: pd.DataFrame) -> None:
        """Query on an exact match date returns the post-match rating."""
        result = engine.compute_ratings(simple_matches)
        ratings = EloEngine.get_ratings_at(result.history, "2024-08-10")
        assert "TeamA" in ratings
        assert "TeamB" in ratings
        # TeamC hasn't played yet on 2024-08-10
        assert "TeamC" not in ratings

    def test_between_dates(self, engine: EloEngine, simple_matches: pd.DataFrame) -> None:
        """Query between match dates returns the most recent rating."""
        result = engine.compute_ratings(simple_matches)
        # 2024-08-12 is between match 1 (08-10) and match 2 (08-17)
        ratings = EloEngine.get_ratings_at(result.history, "2024-08-12")
        assert "TeamA" in ratings
        assert "TeamB" in ratings
        assert "TeamC" not in ratings

    def test_before_any_data(self, engine: EloEngine, simple_matches: pd.DataFrame) -> None:
        """Query before first match returns empty dict."""
        result = engine.compute_ratings(simple_matches)
        ratings = EloEngine.get_ratings_at(result.history, "2020-01-01")
        assert ratings == {}

    def test_after_all_data(self, engine: EloEngine, simple_matches: pd.DataFrame) -> None:
        """Query after last match returns final ratings for all teams."""
        result = engine.compute_ratings(simple_matches)
        ratings = EloEngine.get_ratings_at(result.history, "2025-01-01")
        assert len(ratings) == 3
        for team in ["TeamA", "TeamB", "TeamC"]:
            assert ratings[team] == pytest.approx(result.ratings[team])

    def test_string_and_timestamp_equivalent(
        self, engine: EloEngine, simple_matches: pd.DataFrame,
    ) -> None:
        """String date and pd.Timestamp give the same result."""
        result = engine.compute_ratings(simple_matches)
        r_str = EloEngine.get_ratings_at(result.history, "2024-08-17")
        r_ts = EloEngine.get_ratings_at(result.history, pd.Timestamp("2024-08-17"))
        assert r_str == r_ts

    def test_multi_season(
        self, engine: EloEngine, multi_season_matches: pd.DataFrame,
    ) -> None:
        """Query mid-way through multi-season data returns correct snapshot."""
        result = engine.compute_ratings(multi_season_matches)
        # After first season (2023-08-17) but before second (2024-08-10)
        ratings = EloEngine.get_ratings_at(result.history, "2024-01-01")
        assert "TeamA" in ratings
        assert "TeamB" in ratings
        assert "NewTeam" not in ratings  # hasn't appeared yet


# ---------------------------------------------------------------------------
# Additional edge cases
# ---------------------------------------------------------------------------
class TestExtremeScorelines:
    """Test with extreme goal differences."""

    def test_10_0_scoreline(self, engine: EloEngine) -> None:
        """10-0 win should produce large but finite delta."""
        new_h, new_a, dh, da = engine.elo_update(1500, 1500, "H", 10, 0)
        assert math.isfinite(dh)
        assert dh > 0
        assert abs(dh) > abs(engine.elo_update(1500, 1500, "H", 1, 0)[2])

    def test_0_10_scoreline(self, engine: EloEngine) -> None:
        """0-10 away win should produce large negative delta for home."""
        _, _, dh, da = engine.elo_update(1500, 1500, "A", 0, 10)
        assert dh < 0
        assert da > 0
        assert math.isfinite(dh)

    def test_20_19_scoreline(self, engine: EloEngine) -> None:
        """Absurd scoreline still produces valid output."""
        new_h, new_a, dh, da = engine.elo_update(1500, 1500, "H", 20, 19)
        assert math.isfinite(new_h)
        assert math.isfinite(new_a)
        assert dh > 0  # home won

    def test_0_0_draw_no_mov(self, engine: EloEngine) -> None:
        """0-0 draw should use base K (no MoV multiplier)."""
        _, _, dh, _ = engine.elo_update(1500, 1500, "D", 0, 0)
        assert math.isfinite(dh)


class TestLongTimeGaps:
    """Test time decay with very long gaps."""

    def test_10_year_gap(self, engine: EloEngine) -> None:
        """Rating should decay significantly over 10 years."""
        ratings = {"TeamA": 1800.0}
        last = {"TeamA": pd.Timestamp("2010-01-01")}
        engine.apply_time_decay("TeamA", pd.Timestamp("2020-01-01"), ratings, last)
        # Should be closer to 1500 after 10 years (with decay_rate=0.95)
        assert ratings["TeamA"] < 1750

    def test_1_day_gap_minimal_decay(self, engine: EloEngine) -> None:
        """1-day gap should barely affect rating."""
        ratings = {"TeamA": 1700.0}
        last = {"TeamA": pd.Timestamp("2024-01-01")}
        engine.apply_time_decay("TeamA", pd.Timestamp("2024-01-02"), ratings, last)
        assert ratings["TeamA"] > 1699

    def test_negative_time_gap_no_decay(self, engine: EloEngine) -> None:
        """Negative gap (match before last match) should not decay."""
        ratings = {"TeamA": 1700.0}
        last = {"TeamA": pd.Timestamp("2024-06-01")}
        engine.apply_time_decay("TeamA", pd.Timestamp("2024-01-01"), ratings, last)
        assert ratings["TeamA"] == 1700.0


class TestRatingFloor:
    """Test behavior at extreme low ratings."""

    def test_very_low_rating_team(self, engine: EloEngine) -> None:
        """Team with rating near 0 should still produce valid updates."""
        new_h, new_a, dh, da = engine.elo_update(100, 1500, "A", 0, 5)
        assert math.isfinite(new_h)
        assert math.isfinite(new_a)
        assert new_h < 100  # home lost, should go even lower

    def test_very_high_vs_very_low(self, engine: EloEngine) -> None:
        """Extreme rating gap should not produce NaN."""
        new_h, new_a, dh, da = engine.elo_update(2500, 500, "H", 5, 0)
        assert math.isfinite(new_h)
        assert math.isfinite(new_a)
        # Expected win by favorite → small delta
        assert abs(dh) < 5


class TestTierBoundary:
    """Test tier weight edge cases."""

    def test_unknown_tier_defaults_to_1(self) -> None:
        """Unknown tier should use weight 1.0."""
        from src.config import EloSettings
        s = EloSettings()
        assert s.tier_weight(99) == 1.0
        assert s.tier_weight(0) == 1.0

    def test_tier_1_vs_tier_5_ratio(self) -> None:
        """Tier 1 update should be 1.5x tier 5."""
        from src.config import EloSettings
        engine = EloEngine(EloSettings())
        _, _, dh_t1, _ = engine.elo_update(1500, 1500, "H", 1, 0, tier=1)
        _, _, dh_t5, _ = engine.elo_update(1500, 1500, "H", 1, 0, tier=5)
        assert abs(dh_t1 / dh_t5) == pytest.approx(1.5, abs=0.01)
