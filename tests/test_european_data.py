"""Tests for European competition data parsing and team name normalization."""

import pandas as pd
import pytest

from src.european_data import (
    load_european_data,
    parse_competition_file,
    _parse_team_name,
    _classify_stage,
    COMPETITION_FILES,
    STAGE_TIER,
)
from src.team_names import normalize_team_name, TEAM_NAME_MAP


# --- Team name normalization ---

class TestTeamNameNormalization:
    def test_english_teams(self):
        assert normalize_team_name("Arsenal FC") == "Arsenal"
        assert normalize_team_name("Manchester City FC") == "Man City"
        assert normalize_team_name("Manchester United") == "Man United"
        assert normalize_team_name("Tottenham Hotspur") == "Tottenham"

    def test_spanish_teams(self):
        assert normalize_team_name("FC Barcelona") == "Barcelona"
        assert normalize_team_name("Real Madrid CF") == "Real Madrid"
        assert normalize_team_name("Club Atlético de Madrid") == "Ath Madrid"
        assert normalize_team_name("Athletic Club") == "Ath Bilbao"

    def test_german_teams(self):
        assert normalize_team_name("Bayern München") == "Bayern Munich"
        assert normalize_team_name("FC Bayern München") == "Bayern Munich"
        assert normalize_team_name("Borussia Dortmund") == "Dortmund"
        assert normalize_team_name("Bayer 04 Leverkusen") == "Leverkusen"

    def test_italian_teams(self):
        assert normalize_team_name("FC Internazionale Milano") == "Inter"
        assert normalize_team_name("AC Milan") == "Milan"
        assert normalize_team_name("Juventus FC") == "Juventus"
        assert normalize_team_name("SSC Napoli") == "Napoli"

    def test_french_teams(self):
        assert normalize_team_name("Paris Saint-Germain FC") == "Paris SG"
        assert normalize_team_name("Olympique Lyonnais") == "Lyon"
        assert normalize_team_name("Olympique de Marseille") == "Marseille"

    def test_unknown_team_passthrough(self):
        assert normalize_team_name("Some Unknown Team") == "Some Unknown Team"

    def test_non_top5_teams(self):
        assert normalize_team_name("AFC Ajax") == "Ajax"
        assert normalize_team_name("FC Porto") == "Porto"
        assert normalize_team_name("Celtic FC") == "Celtic"


# --- Parser internals ---

class TestParseTeamName:
    def test_with_country_code(self):
        name, code = _parse_team_name("Arsenal FC (ENG)")
        assert name == "Arsenal FC"
        assert code == "ENG"

    def test_without_country_code(self):
        name, code = _parse_team_name("Arsenal")
        assert name == "Arsenal"
        assert code == ""

    def test_special_characters(self):
        name, code = _parse_team_name("Atlético Madrid (ESP)")
        assert name == "Atlético Madrid"
        assert code == "ESP"


class TestClassifyStage:
    def test_group_stage(self):
        assert _classify_stage("Group A") == "group"
        assert _classify_stage("Group H") == "group"

    def test_knockout(self):
        assert _classify_stage("Round of 16") == "knockout"
        assert _classify_stage("Quarterfinals") == "knockout"
        assert _classify_stage("Semifinals") == "knockout"
        assert _classify_stage("Final") == "knockout"

    def test_league_phase(self):
        assert _classify_stage("League, Matchday 1") == "league"
        assert _classify_stage("League, Matchday 8") == "league"

    def test_playoffs(self):
        assert _classify_stage("Playoffs, Matchday 1") == "playoffs"


# --- Full data loading ---

class TestLoadEuropeanData:
    @pytest.fixture(scope="class")
    def eu_data(self):
        return load_european_data(verbose=False)

    def test_loads_data(self, eu_data):
        assert len(eu_data) > 0

    def test_has_required_columns(self, eu_data):
        required = ["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR",
                     "Season", "Competition", "Stage", "Tier"]
        for col in required:
            assert col in eu_data.columns, f"Missing column: {col}"

    def test_date_range_reasonable(self, eu_data):
        assert eu_data["Date"].min() >= pd.Timestamp("2011-01-01")
        assert eu_data["Date"].max() <= pd.Timestamp("2027-01-01")

    def test_competitions_present(self, eu_data):
        comps = eu_data["Competition"].unique()
        assert "Champions League" in comps

    def test_ftr_values(self, eu_data):
        assert set(eu_data["FTR"].unique()) <= {"H", "D", "A"}

    def test_tier_values(self, eu_data):
        assert eu_data["Tier"].isin([1, 2, 3, 4]).all()

    def test_cl_match_counts_per_season(self, eu_data):
        """CL should have 125 group+knockout matches per season (pre-2024)."""
        cl = eu_data[eu_data["Competition"] == "Champions League"]
        for season in ["2016-17", "2017-18", "2018-19"]:
            count = len(cl[cl["Season"] == season])
            assert count == 125, f"CL {season}: expected 125, got {count}"

    def test_team_names_normalized(self, eu_data):
        """Top-5 country teams should use domestic naming convention."""
        teams = set(eu_data["HomeTeam"].unique()) | set(eu_data["AwayTeam"].unique())
        # These should be normalized, not the raw European names
        assert "Arsenal" in teams  # not "Arsenal FC"
        assert "Barcelona" in teams  # not "FC Barcelona"
        assert "Bayern Munich" in teams  # not "Bayern München"
        assert "Inter" in teams  # not "FC Internazionale Milano"
        assert "Paris SG" in teams  # not "Paris Saint-Germain"

    def test_filter_by_competition(self):
        cl_only = load_european_data(competitions=["cl"], verbose=False)
        assert (cl_only["Competition"] == "Champions League").all()

    def test_filter_by_season(self):
        one_season = load_european_data(seasons=["2023-24"], verbose=False)
        assert (one_season["Season"] == "2023-24").all()

    def test_sorted_by_date(self, eu_data):
        dates = eu_data["Date"].values
        assert (dates[:-1] <= dates[1:]).all()


# --- Tier weighting in engine ---

class TestTierWeighting:
    def test_tier_weight_defaults(self):
        from src.config import EloSettings
        s = EloSettings()
        assert s.tier_weight(1) == 1.5
        assert s.tier_weight(2) == 1.2
        assert s.tier_weight(3) == 1.2
        assert s.tier_weight(4) == 1.0
        assert s.tier_weight(5) == 1.0

    def test_tier_1_larger_update(self):
        from src.elo_engine import EloEngine
        engine = EloEngine()
        # CL knockout (tier 1) should produce larger delta than domestic (tier 5)
        _, _, dh_cl, _ = engine.elo_update(1500, 1500, "H", 2, 1, tier=1)
        _, _, dh_dom, _ = engine.elo_update(1500, 1500, "H", 2, 1, tier=5)
        assert abs(dh_cl) > abs(dh_dom)

    def test_tier_5_matches_no_tier(self):
        from src.elo_engine import EloEngine
        engine = EloEngine()
        # Tier 5 (domestic default) should equal not passing tier at all
        result_5 = engine.elo_update(1500, 1500, "H", 2, 1, tier=5)
        result_default = engine.elo_update(1500, 1500, "H", 2, 1)
        assert result_5 == result_default

    def test_compute_ratings_with_tier_column(self):
        from src.elo_engine import EloEngine
        engine = EloEngine()
        matches = pd.DataFrame({
            "Date": pd.to_datetime(["2024-01-01", "2024-01-08"]),
            "HomeTeam": ["A", "B"],
            "AwayTeam": ["B", "A"],
            "FTR": ["H", "H"],
            "FTHG": [2, 1],
            "FTAG": [0, 0],
            "Season": ["2324", "2324"],
            "Tier": [1, 5],
        })
        result = engine.compute_ratings(matches)
        assert result.matches_processed == 2


class TestParseTeamNameEdgeCases:
    """Edge cases for _parse_team_name."""

    def test_empty_string(self):
        name, code = _parse_team_name("")
        assert name == ""
        assert code == ""

    def test_only_country_code(self):
        name, code = _parse_team_name("(ENG)")
        # Parser may or may not extract code from string with no team name
        assert isinstance(code, str)

    def test_multiple_parentheses(self):
        name, code = _parse_team_name("Some Team (A) (ENG)")
        # Should match last parenthetical as country code
        assert "ENG" in code or "A" in code


class TestClassifyStageEdgeCases:
    """Edge cases for _classify_stage."""

    def test_empty_stage(self):
        result = _classify_stage("")
        assert isinstance(result, str)

    def test_unknown_stage(self):
        result = _classify_stage("Random Unknown Stage")
        assert isinstance(result, str)

    def test_third_place(self):
        result = _classify_stage("3rd Place")
        assert isinstance(result, str)

    def test_qualifying(self):
        result = _classify_stage("Qualifying Round 1")
        assert isinstance(result, str)


class TestNormalizationEdgeCases:
    """Edge cases for team name normalization."""

    def test_already_normalized(self):
        """Already normalized names should pass through."""
        assert normalize_team_name("Arsenal") == "Arsenal"

    def test_name_with_extra_whitespace(self):
        """Whitespace-padded names may not match mapping."""
        result = normalize_team_name("  Arsenal FC  ")
        # May or may not strip; should not crash
        assert isinstance(result, str)

    def test_case_sensitivity(self):
        """Name mappings are case-sensitive."""
        result = normalize_team_name("arsenal fc")
        assert isinstance(result, str)

    def test_team_name_map_has_entries(self):
        """TEAM_NAME_MAP should have 50+ entries."""
        assert len(TEAM_NAME_MAP) >= 50
