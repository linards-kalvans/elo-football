"""Tests for team mapping between football-data.org and internal names."""

import sqlite3

import pytest

from src.live.team_mapping import (
    FOOTBALL_DATA_ORG_NAMES,
    find_best_match,
    get_all_mappings,
    get_mapping,
    get_unmapped_teams,
    normalize_name,
    resolve_team,
    save_mapping,
)


# --- normalize_name tests ---


class TestNormalizeName:
    """Tests for normalize_name()."""

    def test_lowercase(self):
        assert normalize_name("Arsenal") == "arsenal"

    def test_strip_fc_suffix(self):
        assert normalize_name("Arsenal FC") == "arsenal"

    def test_strip_afc_suffix(self):
        assert normalize_name("Bournemouth AFC") == "bournemouth"

    def test_strip_cf_suffix(self):
        assert normalize_name("Valencia CF") == "valencia"

    def test_strip_fc_prefix(self):
        assert normalize_name("FC Barcelona") == "barcelona"

    def test_strip_ac_prefix(self):
        assert normalize_name("AC Milan") == "milan"

    def test_strip_vfb_prefix(self):
        assert normalize_name("VfB Stuttgart") == "stuttgart"

    def test_remove_accents(self):
        result = normalize_name("Atlético Madrid")
        assert result == "atletico madrid"

    def test_remove_umlaut(self):
        result = normalize_name("Bayern München")
        assert result == "bayern munchen"

    def test_remove_cedilla(self):
        result = normalize_name("Fenerbahçe")
        assert result == "fenerbahce"

    def test_collapse_whitespace(self):
        assert normalize_name("  Man   City  ") == "man city"

    def test_empty_string(self):
        assert normalize_name("") == ""

    def test_no_change_needed(self):
        assert normalize_name("Brighton") == "brighton"

    def test_combined_transformations(self):
        # FC prefix + accents + suffix
        result = normalize_name("FC Bayern München")
        assert result == "bayern munchen"

    def test_strip_year_suffix(self):
        result = normalize_name("Bologna FC 1909")
        # After stripping " fc" and " 1909"
        assert "bologna" in result


# --- find_best_match tests ---


class TestFindBestMatch:
    """Tests for find_best_match()."""

    KNOWN_TEAMS = [
        "Arsenal", "Man United", "Man City", "Chelsea", "Liverpool",
        "Tottenham", "Bayern Munich", "Dortmund", "Barcelona",
        "Real Madrid", "Paris SG", "Juventus", "Inter", "Milan",
        "Nott'm Forest", "Wolves", "Brighton", "Ein Frankfurt",
        "M'gladbach", "Ath Madrid", "Ath Bilbao",
    ]

    def test_exact_match(self):
        result = find_best_match("Arsenal", self.KNOWN_TEAMS)
        assert result == "Arsenal"

    def test_close_match(self):
        result = find_best_match("Bayern Munchen", self.KNOWN_TEAMS)
        assert result == "Bayern Munich"

    def test_suffix_stripped_match(self):
        # After normalization, "Arsenal FC" -> "arsenal" matches
        # "Arsenal" -> "arsenal" exactly (FC suffix stripped).
        result = find_best_match("Arsenal FC", self.KNOWN_TEAMS)
        assert result == "Arsenal"

    def test_no_match_below_threshold(self):
        result = find_best_match("Completely Unknown Team", self.KNOWN_TEAMS, threshold=0.9)
        assert result is None

    def test_custom_threshold(self):
        # With a very low threshold, even bad matches should return something
        result = find_best_match("XYZ", self.KNOWN_TEAMS, threshold=0.0)
        assert result is not None

    def test_empty_known_teams(self):
        result = find_best_match("Arsenal", [])
        assert result is None


# --- resolve_team tests ---


class TestResolveTeam:
    """Tests for resolve_team()."""

    KNOWN_TEAMS = [
        "Arsenal", "Man United", "Man City", "Chelsea", "Liverpool",
        "Tottenham", "Bayern Munich", "Dortmund", "Barcelona",
        "Real Madrid", "Paris SG", "Juventus", "Inter", "Milan",
        "Wolves", "Brighton", "Nott'm Forest", "West Ham",
        "Newcastle", "Leicester", "Bournemouth",
    ]

    def test_known_mapping(self):
        result = resolve_team("Manchester United FC", self.KNOWN_TEAMS)
        assert result == "Man United"

    def test_known_mapping_city(self):
        result = resolve_team("Manchester City FC", self.KNOWN_TEAMS)
        assert result == "Man City"

    def test_known_mapping_wolves(self):
        result = resolve_team("Wolverhampton Wanderers FC", self.KNOWN_TEAMS)
        assert result == "Wolves"

    def test_known_mapping_nottm_forest(self):
        result = resolve_team("Nottingham Forest FC", self.KNOWN_TEAMS)
        assert result == "Nott'm Forest"

    def test_known_mapping_bayern(self):
        result = resolve_team("FC Bayern München", self.KNOWN_TEAMS)
        assert result == "Bayern Munich"

    def test_known_mapping_psg(self):
        result = resolve_team("Paris Saint-Germain FC", self.KNOWN_TEAMS)
        assert result == "Paris SG"

    def test_exact_name_in_db(self):
        result = resolve_team("Arsenal", self.KNOWN_TEAMS)
        assert result == "Arsenal"

    def test_fuzzy_fallback(self):
        # A name not in known mappings but close enough for fuzzy match
        result = resolve_team("Juventus Turin", self.KNOWN_TEAMS)
        assert result == "Juventus"

    def test_no_match(self):
        result = resolve_team("FC Totally Unknown 1903", self.KNOWN_TEAMS, threshold=0.9)
        assert result is None


# --- FOOTBALL_DATA_ORG_NAMES coverage tests ---


class TestKnownMappings:
    """Tests for the FOOTBALL_DATA_ORG_NAMES dictionary."""

    def test_has_premier_league_teams(self):
        pl_teams = [
            "Manchester United FC", "Manchester City FC",
            "Tottenham Hotspur FC", "Newcastle United FC",
            "Wolverhampton Wanderers FC", "West Ham United FC",
            "Brighton & Hove Albion FC", "Nottingham Forest FC",
            "AFC Bournemouth", "Arsenal FC", "Chelsea FC",
            "Liverpool FC",
        ]
        for team in pl_teams:
            assert team in FOOTBALL_DATA_ORG_NAMES, f"Missing PL team: {team}"

    def test_has_la_liga_teams(self):
        la_liga_teams = [
            "Club Atlético de Madrid", "Athletic Club",
            "FC Barcelona", "Real Madrid CF", "Sevilla FC",
            "Villarreal CF", "Valencia CF",
        ]
        for team in la_liga_teams:
            assert team in FOOTBALL_DATA_ORG_NAMES, f"Missing La Liga team: {team}"

    def test_has_bundesliga_teams(self):
        bl_teams = [
            "FC Bayern München", "Borussia Dortmund",
            "Bayer 04 Leverkusen", "RB Leipzig",
            "Eintracht Frankfurt", "VfL Wolfsburg",
        ]
        for team in bl_teams:
            assert team in FOOTBALL_DATA_ORG_NAMES, f"Missing BL team: {team}"

    def test_has_serie_a_teams(self):
        sa_teams = [
            "AC Milan", "FC Internazionale Milano",
            "Juventus FC", "SSC Napoli", "AS Roma", "SS Lazio",
        ]
        for team in sa_teams:
            assert team in FOOTBALL_DATA_ORG_NAMES, f"Missing SA team: {team}"

    def test_has_ligue1_teams(self):
        fl1_teams = [
            "Paris Saint-Germain FC", "Olympique de Marseille",
            "Olympique Lyonnais", "AS Monaco FC", "LOSC Lille",
        ]
        for team in fl1_teams:
            assert team in FOOTBALL_DATA_ORG_NAMES, f"Missing FL1 team: {team}"

    def test_has_cl_teams(self):
        cl_teams = [
            "AFC Ajax", "FC Porto", "SL Benfica", "Celtic FC",
        ]
        for team in cl_teams:
            assert team in FOOTBALL_DATA_ORG_NAMES, f"Missing CL team: {team}"

    def test_mappings_are_non_empty(self):
        for api_name, internal_name in FOOTBALL_DATA_ORG_NAMES.items():
            assert api_name.strip(), "Empty API name"
            assert internal_name.strip(), f"Empty internal name for {api_name}"

    def test_no_duplicate_values_per_source(self):
        # Multiple API names can map to the same internal name, that's fine
        # But each API name should be unique (it's a dict, so enforced)
        assert len(FOOTBALL_DATA_ORG_NAMES) == len(
            set(FOOTBALL_DATA_ORG_NAMES.keys())
        )

    def test_minimum_mapping_count(self):
        # We should have mappings for at least 100 teams
        assert len(FOOTBALL_DATA_ORG_NAMES) >= 100


# --- Database operation tests ---


@pytest.fixture
def mapping_db():
    """Create an in-memory database with schema for mapping tests."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    # Create teams table
    conn.execute("""
        CREATE TABLE teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            country TEXT NOT NULL DEFAULT '',
            aliases TEXT NOT NULL DEFAULT '[]'
        )
    """)

    # Create api_team_mappings table
    conn.execute("""
        CREATE TABLE api_team_mappings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            api_source TEXT NOT NULL,
            api_team_id INTEGER NOT NULL,
            api_team_name TEXT NOT NULL,
            team_id INTEGER NOT NULL REFERENCES teams(id),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(api_source, api_team_id)
        )
    """)

    # Seed some teams
    conn.execute("INSERT INTO teams (name, country) VALUES ('Arsenal', 'England')")
    conn.execute("INSERT INTO teams (name, country) VALUES ('Chelsea', 'England')")
    conn.execute("INSERT INTO teams (name, country) VALUES ('Bayern Munich', 'Germany')")
    conn.execute("INSERT INTO teams (name, country) VALUES ('Man United', 'England')")
    conn.execute("INSERT INTO teams (name, country) VALUES ('Man City', 'England')")
    conn.commit()

    yield conn
    conn.close()


class TestDatabaseOperations:
    """Tests for DB mapping operations."""

    def test_save_and_get_mapping(self, mapping_db):
        save_mapping(mapping_db, "football-data.org", 57, "Arsenal FC", 1)
        result = get_mapping(mapping_db, "football-data.org", 57)
        assert result == 1

    def test_get_mapping_not_found(self, mapping_db):
        result = get_mapping(mapping_db, "football-data.org", 9999)
        assert result is None

    def test_save_mapping_update(self, mapping_db):
        """Test that saving a mapping with the same API ID updates it."""
        save_mapping(mapping_db, "football-data.org", 57, "Arsenal FC", 1)
        save_mapping(mapping_db, "football-data.org", 57, "Arsenal FC Updated", 1)
        result = get_mapping(mapping_db, "football-data.org", 57)
        assert result == 1

    def test_save_mapping_different_sources(self, mapping_db):
        """Same API team ID but different sources should be separate."""
        save_mapping(mapping_db, "football-data.org", 57, "Arsenal FC", 1)
        save_mapping(mapping_db, "other-api.com", 57, "Arsenal", 1)

        result1 = get_mapping(mapping_db, "football-data.org", 57)
        result2 = get_mapping(mapping_db, "other-api.com", 57)
        assert result1 == 1
        assert result2 == 1

    def test_get_all_mappings(self, mapping_db):
        save_mapping(mapping_db, "football-data.org", 57, "Arsenal FC", 1)
        save_mapping(mapping_db, "football-data.org", 61, "Chelsea FC", 2)

        mappings = get_all_mappings(mapping_db, "football-data.org")
        assert len(mappings) == 2
        names = {m["team_name"] for m in mappings}
        assert names == {"Arsenal", "Chelsea"}

    def test_get_all_mappings_empty(self, mapping_db):
        mappings = get_all_mappings(mapping_db, "football-data.org")
        assert mappings == []

    def test_get_all_mappings_filters_by_source(self, mapping_db):
        save_mapping(mapping_db, "football-data.org", 57, "Arsenal FC", 1)
        save_mapping(mapping_db, "other-api.com", 100, "Arsenal", 1)

        mappings = get_all_mappings(mapping_db, "football-data.org")
        assert len(mappings) == 1

    def test_get_unmapped_teams_empty_when_all_mapped(self, mapping_db):
        save_mapping(mapping_db, "football-data.org", 57, "Arsenal FC", 1)
        unmapped = get_unmapped_teams(mapping_db, "football-data.org")
        assert unmapped == []

    def test_multiple_teams_mapping(self, mapping_db):
        save_mapping(mapping_db, "football-data.org", 57, "Arsenal FC", 1)
        save_mapping(mapping_db, "football-data.org", 61, "Chelsea FC", 2)
        save_mapping(mapping_db, "football-data.org", 5, "FC Bayern München", 3)

        assert get_mapping(mapping_db, "football-data.org", 57) == 1
        assert get_mapping(mapping_db, "football-data.org", 61) == 2
        assert get_mapping(mapping_db, "football-data.org", 5) == 3


# --- Integration test: known mappings match real DB names ---


class TestMappingIntegration:
    """Test that known mappings produce valid internal names."""

    # A subset of actual team names from the database
    REAL_DB_TEAMS = [
        "Arsenal", "Man United", "Man City", "Chelsea", "Liverpool",
        "Tottenham", "Newcastle", "Wolves", "West Ham", "Brighton",
        "Nott'm Forest", "Bournemouth", "Leicester", "Crystal Palace",
        "Everton", "Fulham", "Brentford", "Ipswich", "Southampton",
        "Barcelona", "Real Madrid", "Ath Madrid", "Ath Bilbao",
        "Sevilla", "Villarreal", "Betis", "Sociedad", "Valencia",
        "Bayern Munich", "Dortmund", "Leverkusen", "RB Leipzig",
        "Ein Frankfurt", "Wolfsburg", "Freiburg", "M'gladbach",
        "Juventus", "Inter", "Milan", "Napoli", "Roma", "Lazio",
        "Fiorentina", "Atalanta", "Bologna",
        "Paris SG", "Marseille", "Lyon", "Monaco", "Lille", "Nice",
        "Lens", "Rennes", "Brest",
    ]

    def test_major_mappings_resolve_correctly(self):
        major_api_names = [
            "Manchester United FC", "Manchester City FC",
            "Wolverhampton Wanderers FC", "Nottingham Forest FC",
            "FC Bayern München", "Paris Saint-Germain FC",
            "FC Internazionale Milano", "AC Milan",
            "Club Atlético de Madrid", "FC Barcelona",
        ]
        for api_name in major_api_names:
            result = resolve_team(api_name, self.REAL_DB_TEAMS)
            assert result is not None, f"Failed to resolve: {api_name}"
            assert result in self.REAL_DB_TEAMS, (
                f"{api_name} resolved to '{result}' which is not in DB teams"
            )
