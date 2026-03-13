"""Multi-league data loading utilities for top-5 European domestic leagues.

This module provides clean interfaces for loading match data from Football-Data.co.uk
CSVs for the Premier League, La Liga, Bundesliga, Serie A, and Ligue 1.

All DataFrames include standardized columns:
    Date, HomeTeam, AwayTeam, FTHG, FTAG, FTR, Season, League

Date format: DD/MM/YYYY (parsed with dayfirst=True)
FTR values: H (home win), D (draw), A (away win)
"""

from pathlib import Path
from typing import Optional

import pandas as pd


# League metadata configuration
LEAGUE_CONFIG = {
    "epl": {"code": "E0", "country": "England", "name": "Premier League"},
    "laliga": {"code": "SP1", "country": "Spain", "name": "La Liga"},
    "bundesliga": {"code": "D1", "country": "Germany", "name": "Bundesliga"},
    "seriea": {"code": "I1", "country": "Italy", "name": "Serie A"},
    "ligue1": {"code": "F1", "country": "France", "name": "Ligue 1"},
}

# Columns required for Elo computation
ESSENTIAL_COLS = ["Date", "HomeTeam", "AwayTeam", "FTR"]

# Columns to retain in output
OUTPUT_COLS = ["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR", "Season", "League"]


def load_league(
    league_key: str,
    data_dir: str = "data",
    seasons: Optional[list[str]] = None,
    verbose: bool = True,
) -> pd.DataFrame:
    """Load all seasons for a single league from Football-Data.co.uk CSVs.

    Args:
        league_key: League identifier (epl, laliga, bundesliga, seriea, ligue1)
        data_dir: Root directory containing league subdirectories
        seasons: List of season codes (e.g., ["1617", "1718"]). If None, loads all available.
        verbose: Print summary statistics if True

    Returns:
        DataFrame with columns: Date, HomeTeam, AwayTeam, FTHG, FTAG, FTR, Season, League
        Empty DataFrame if league not found or no data available.

    Raises:
        ValueError: If league_key is not recognized
    """
    if league_key not in LEAGUE_CONFIG:
        raise ValueError(
            f"Unknown league '{league_key}'. Valid leagues: {list(LEAGUE_CONFIG.keys())}"
        )

    config = LEAGUE_CONFIG[league_key]
    league_path = Path(data_dir) / league_key
    code = config["code"]

    if not league_path.exists():
        if verbose:
            print(f"Warning: League directory not found: {league_path}")
        return pd.DataFrame(columns=OUTPUT_COLS)

    # Discover season directories
    season_dirs = sorted([d for d in league_path.iterdir() if d.is_dir()])
    if seasons is not None:
        season_dirs = [d for d in season_dirs if d.name in seasons]

    if not season_dirs:
        if verbose:
            print(f"Warning: No season data found for {league_key}")
        return pd.DataFrame(columns=OUTPUT_COLS)

    # Load all CSVs
    dfs = []
    for season_dir in season_dirs:
        csv_path = season_dir / f"{code}.csv"
        if not csv_path.exists():
            continue

        try:
            df = pd.read_csv(csv_path, encoding="utf-8", low_memory=False)

            # Check for essential columns
            missing = [col for col in ESSENTIAL_COLS if col not in df.columns]
            if missing:
                if verbose:
                    print(f"Skipping {csv_path}: missing columns {missing}")
                continue

            # Parse dates — DD/MM/YYYY is the standard format from Football-Data
            df["Date"] = pd.to_datetime(
                df["Date"], format="mixed", dayfirst=True, errors="coerce",
            )

            # Select output columns first (avoid fragmentation), then add metadata
            available_cols = [col for col in OUTPUT_COLS if col in df.columns and col not in ("Season", "League")]
            df = df[available_cols].copy()
            df["Season"] = season_dir.name
            df["League"] = config["name"]

            # Drop rows with missing essential data
            df = df.dropna(subset=ESSENTIAL_COLS)

            dfs.append(df)

        except Exception as e:
            if verbose:
                print(f"Error loading {csv_path}: {e}")
            continue

    if not dfs:
        if verbose:
            print(f"No valid data loaded for {league_key}")
        return pd.DataFrame(columns=OUTPUT_COLS)

    # Combine all seasons
    result = pd.concat(dfs, ignore_index=True)
    result = result.sort_values("Date").reset_index(drop=True)

    if verbose:
        print(f"\n{config['name']} ({league_key}):")
        print(f"  Seasons: {len(season_dirs)}")
        print(f"  Matches: {len(result)}")
        print(f"  Teams: {len(result['HomeTeam'].unique())}")
        print(f"  Date range: {result['Date'].min().date()} to {result['Date'].max().date()}")

    return result


def load_all_leagues(
    data_dir: str = "data",
    leagues: Optional[list[str]] = None,
    verbose: bool = True,
) -> dict[str, pd.DataFrame]:
    """Load all available leagues from Football-Data.co.uk CSVs.

    Args:
        data_dir: Root directory containing league subdirectories
        leagues: List of league keys to load. If None, loads all configured leagues.
        verbose: Print summary statistics if True

    Returns:
        Dictionary mapping league_key -> DataFrame
        Leagues with no data are excluded from the result.
    """
    if leagues is None:
        leagues = list(LEAGUE_CONFIG.keys())

    if verbose:
        print(f"Loading leagues: {leagues}")
        print(f"Data directory: {data_dir}\n")

    results = {}
    for league_key in leagues:
        try:
            df = load_league(league_key, data_dir=data_dir, verbose=verbose)
            if not df.empty:
                results[league_key] = df
        except Exception as e:
            if verbose:
                print(f"Error loading {league_key}: {e}")
            continue

    if verbose:
        print(f"\n{'='*60}")
        print(f"Total leagues loaded: {len(results)}")
        total_matches = sum(len(df) for df in results.values())
        print(f"Total matches: {total_matches}")
        print(f"{'='*60}\n")

    return results


def get_league_info(league_key: str) -> dict[str, str]:
    """Get metadata for a league.

    Args:
        league_key: League identifier

    Returns:
        Dictionary with keys: code, country, name

    Raises:
        ValueError: If league_key is not recognized
    """
    if league_key not in LEAGUE_CONFIG:
        raise ValueError(
            f"Unknown league '{league_key}'. Valid leagues: {list(LEAGUE_CONFIG.keys())}"
        )
    return LEAGUE_CONFIG[league_key].copy()
