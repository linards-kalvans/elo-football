"""Tests for multi-league data loading utilities."""

import pandas as pd
import pytest

from src.data_loader import (
    ESSENTIAL_COLS,
    LEAGUE_CONFIG,
    OUTPUT_COLS,
    get_league_info,
    load_all_leagues,
    load_league,
)


# ---------------------------------------------------------------------------
# Configuration tests
# ---------------------------------------------------------------------------
def test_league_config_structure():
    """Verify LEAGUE_CONFIG has expected structure."""
    assert "epl" in LEAGUE_CONFIG
    assert "laliga" in LEAGUE_CONFIG
    assert "bundesliga" in LEAGUE_CONFIG
    assert "seriea" in LEAGUE_CONFIG
    assert "ligue1" in LEAGUE_CONFIG

    for league_key, config in LEAGUE_CONFIG.items():
        assert "code" in config
        assert "country" in config
        assert "name" in config
        assert isinstance(config["code"], str)
        assert isinstance(config["country"], str)
        assert isinstance(config["name"], str)


def test_get_league_info():
    """Test get_league_info returns correct metadata."""
    epl_info = get_league_info("epl")
    assert epl_info["code"] == "E0"
    assert epl_info["country"] == "England"
    assert epl_info["name"] == "Premier League"

    with pytest.raises(ValueError, match="Unknown league"):
        get_league_info("invalid_league")


# ---------------------------------------------------------------------------
# EPL data loading tests (known to exist)
# ---------------------------------------------------------------------------
def test_load_epl_basic():
    """Test loading EPL data returns non-empty DataFrame."""
    df = load_league("epl", verbose=False)

    # Should have data
    assert not df.empty, "EPL data should exist"
    assert len(df) > 0

    # Should have all required columns
    for col in OUTPUT_COLS:
        assert col in df.columns, f"Missing column: {col}"


def test_load_epl_essential_columns():
    """Verify essential columns are present and non-null."""
    df = load_league("epl", verbose=False)

    for col in ESSENTIAL_COLS:
        assert col in df.columns, f"Missing essential column: {col}"
        assert df[col].notna().all(), f"Essential column {col} contains NaN"


def test_load_epl_dates_parsed():
    """Verify dates are parsed correctly to datetime."""
    df = load_league("epl", verbose=False)

    assert pd.api.types.is_datetime64_any_dtype(df["Date"]), "Date column should be datetime"
    assert df["Date"].notna().all(), "Date column should not contain NaN"

    # Check dates are in reasonable range (2016-2026)
    min_year = df["Date"].dt.year.min()
    max_year = df["Date"].dt.year.max()
    assert 2016 <= min_year <= 2026, f"Min year {min_year} out of expected range"
    assert 2016 <= max_year <= 2026, f"Max year {max_year} out of expected range"


def test_load_epl_ftr_values():
    """Verify FTR column contains only valid result codes."""
    df = load_league("epl", verbose=False)

    valid_results = {"H", "D", "A"}
    assert df["FTR"].isin(valid_results).all(), "FTR should only contain H, D, or A"


def test_load_epl_league_column():
    """Verify League column is added and consistent."""
    df = load_league("epl", verbose=False)

    assert "League" in df.columns
    assert (df["League"] == "Premier League").all(), "League column should be 'Premier League'"


def test_load_epl_season_column():
    """Verify Season column is added and formatted correctly."""
    df = load_league("epl", verbose=False)

    assert "Season" in df.columns
    assert df["Season"].notna().all()

    # Season codes should be 4-digit strings (e.g., "1617", "1718")
    assert all(
        len(str(s)) == 4 and str(s).isdigit() for s in df["Season"].unique()
    ), "Season codes should be 4-digit strings"


def test_load_epl_sorted_by_date():
    """Verify DataFrame is sorted by date."""
    df = load_league("epl", verbose=False)

    assert df["Date"].is_monotonic_increasing, "DataFrame should be sorted by Date"


def test_load_epl_team_names():
    """Verify team names are non-empty strings."""
    df = load_league("epl", verbose=False)

    assert df["HomeTeam"].notna().all()
    assert df["AwayTeam"].notna().all()
    assert all(isinstance(team, str) and len(team) > 0 for team in df["HomeTeam"].unique())
    assert all(isinstance(team, str) and len(team) > 0 for team in df["AwayTeam"].unique())


def test_load_epl_goals_numeric():
    """Verify FTHG and FTAG are numeric if present."""
    df = load_league("epl", verbose=False)

    if "FTHG" in df.columns:
        assert pd.api.types.is_numeric_dtype(df["FTHG"]), "FTHG should be numeric"
        assert (df["FTHG"] >= 0).all(), "FTHG should be non-negative"

    if "FTAG" in df.columns:
        assert pd.api.types.is_numeric_dtype(df["FTAG"]), "FTAG should be numeric"
        assert (df["FTAG"] >= 0).all(), "FTAG should be non-negative"


# ---------------------------------------------------------------------------
# Single season loading
# ---------------------------------------------------------------------------
def test_load_epl_single_season():
    """Test loading a specific season."""
    df = load_league("epl", seasons=["2324"], verbose=False)

    assert not df.empty
    assert (df["Season"] == "2324").all()


def test_load_epl_multiple_seasons():
    """Test loading multiple specific seasons."""
    df = load_league("epl", seasons=["2223", "2324"], verbose=False)

    assert not df.empty
    seasons = df["Season"].unique()
    assert set(seasons).issubset({"2223", "2324"})


# ---------------------------------------------------------------------------
# Invalid input handling
# ---------------------------------------------------------------------------
def test_load_invalid_league():
    """Test that invalid league raises ValueError."""
    with pytest.raises(ValueError, match="Unknown league"):
        load_league("invalid_league", verbose=False)


def test_load_nonexistent_directory():
    """Test loading from nonexistent directory returns empty DataFrame."""
    df = load_league("epl", data_dir="/nonexistent/path", verbose=False)

    assert df.empty
    assert list(df.columns) == OUTPUT_COLS


# ---------------------------------------------------------------------------
# Multi-league loading tests
# ---------------------------------------------------------------------------
def test_load_all_leagues_returns_dict():
    """Test load_all_leagues returns dict of DataFrames."""
    result = load_all_leagues(verbose=False)

    assert isinstance(result, dict)
    # EPL should definitely be present
    assert "epl" in result
    assert isinstance(result["epl"], pd.DataFrame)
    assert not result["epl"].empty


def test_load_all_leagues_specific_leagues():
    """Test loading only specific leagues."""
    result = load_all_leagues(leagues=["epl"], verbose=False)

    assert "epl" in result
    # Other leagues should not be in result if they don't exist yet
    # (we only verify what's explicitly loaded)


def test_load_all_leagues_each_has_league_column():
    """Test that each loaded league has League column with correct value."""
    result = load_all_leagues(verbose=False)

    for league_key, df in result.items():
        assert "League" in df.columns
        expected_name = LEAGUE_CONFIG[league_key]["name"]
        assert (df["League"] == expected_name).all()


# ---------------------------------------------------------------------------
# Data consistency tests
# ---------------------------------------------------------------------------
def test_epl_no_duplicate_matches():
    """Test EPL data has no exact duplicate matches."""
    df = load_league("epl", verbose=False)

    # Check for duplicates based on date + teams
    duplicates = df.duplicated(subset=["Date", "HomeTeam", "AwayTeam"], keep=False)
    assert not duplicates.any(), f"Found {duplicates.sum()} duplicate matches"


def test_epl_reasonable_match_counts():
    """Test EPL has reasonable number of matches per season."""
    df = load_league("epl", verbose=False)

    matches_per_season = df.groupby("Season").size()

    # EPL has 20 teams, so ~380 matches per season (some seasons may be incomplete)
    for season, count in matches_per_season.items():
        assert 100 <= count <= 400, f"Season {season} has unexpected match count: {count}"
