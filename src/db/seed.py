#!/usr/bin/env python3
"""Seed the Elo database from existing CSV and openfootball data.

Loads all domestic leagues and European competitions, computes unified Elo
ratings, and persists everything to SQLite.

Usage:
    uv run python src/db/seed.py
"""

import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd

from src.config import EloSettings
from src.data_loader import LEAGUE_CONFIG, load_all_leagues
from src.db.connection import init_db
from src.db.repository import (
    insert_competition,
    insert_match,
    insert_parameters,
    insert_rating,
    insert_team,
    get_match_count,
    get_team_count,
)
from src.elo_engine import EloEngine
from src.european_data import COMPETITION_FILES, STAGE_TIER, load_european_data


def build_unified_dataset() -> pd.DataFrame:
    """Load and merge domestic + European data into a single DataFrame."""
    all_leagues = load_all_leagues(verbose=False)
    domestic_dfs = []
    for league_id, df in all_leagues.items():
        df = df.copy()
        df["Tier"] = 5
        df["Competition"] = df["League"]
        domestic_dfs.append(df)

    domestic = pd.concat(domestic_dfs, ignore_index=True)
    print(f"  Domestic: {len(domestic)} matches across {len(all_leagues)} leagues")

    european = load_european_data(verbose=False)
    if european.empty:
        print("  WARNING: No European data found!")
        return domestic.sort_values("Date").reset_index(drop=True)

    european["League"] = european["Competition"]
    print(f"  European: {len(european)} matches")

    shared_cols = ["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR",
                   "Season", "League", "Competition", "Tier"]
    unified = pd.concat([domestic[shared_cols], european[shared_cols]],
                        ignore_index=True)
    unified = unified.sort_values("Date").reset_index(drop=True)
    print(f"  Total: {len(unified)} matches")
    return unified


def seed_database(db_path: str | Path | None = None) -> None:
    """Populate the database from scratch.

    Args:
        db_path: Path to SQLite database file. Defaults to data/elo.db.
    """
    print("=" * 60)
    print("SEEDING ELO DATABASE")
    print("=" * 60)

    # Initialize schema
    conn = init_db(db_path)
    print("\nSchema initialized.")

    # Load unified dataset
    print("\nLoading match data...")
    unified = build_unified_dataset()

    settings = EloSettings()

    # --- Insert competitions ---
    print("\nInserting competitions...")
    comp_ids: dict[str, int] = {}

    # Domestic leagues
    for key, config in LEAGUE_CONFIG.items():
        comp_id = insert_competition(conn, config["name"], tier=5,
                                     country=config["country"])
        comp_ids[config["name"]] = comp_id

    # European competitions — use highest tier for each competition
    eu_tiers = {}
    for (comp_key, _stage), tier in STAGE_TIER.items():
        comp_name = COMPETITION_FILES[comp_key]
        if comp_name not in eu_tiers or tier < eu_tiers[comp_name]:
            eu_tiers[comp_name] = tier
    for comp_name, tier in eu_tiers.items():
        comp_id = insert_competition(conn, comp_name, tier=tier, country="Europe")
        comp_ids[comp_name] = comp_id

    conn.commit()
    print(f"  {len(comp_ids)} competitions")

    # --- Determine team countries from domestic data ---
    team_countries: dict[str, str] = {}
    for key, config in LEAGUE_CONFIG.items():
        domestic_mask = unified["Competition"] == config["name"]
        for team in pd.concat([
            unified.loc[domestic_mask, "HomeTeam"],
            unified.loc[domestic_mask, "AwayTeam"],
        ]).unique():
            team_countries[team] = config["country"]

    # --- Insert teams ---
    print("Inserting teams...")
    all_teams = set(unified["HomeTeam"].unique()) | set(unified["AwayTeam"].unique())
    team_ids: dict[str, int] = {}
    for team_name in sorted(all_teams):
        country = team_countries.get(team_name, "")
        team_id = insert_team(conn, team_name, country=country)
        team_ids[team_name] = team_id
    conn.commit()
    print(f"  {len(team_ids)} teams")

    # --- Insert matches ---
    print("Inserting matches...")
    match_ids: list[int | None] = []
    inserted = 0
    skipped = 0
    for _, row in unified.iterrows():
        comp_name = row["Competition"]
        comp_id = comp_ids.get(comp_name)
        if comp_id is None:
            skipped += 1
            match_ids.append(None)
            continue

        date_str = pd.Timestamp(row["Date"]).strftime("%Y-%m-%d")
        match_id = insert_match(
            conn,
            date=date_str,
            home_team_id=team_ids[row["HomeTeam"]],
            away_team_id=team_ids[row["AwayTeam"]],
            home_goals=int(row["FTHG"]),
            away_goals=int(row["FTAG"]),
            result=row["FTR"],
            competition_id=comp_id,
            season=row["Season"],
        )
        match_ids.append(match_id)
        if match_id is not None:
            inserted += 1
        else:
            skipped += 1

    conn.commit()
    print(f"  {inserted} matches inserted, {skipped} skipped (duplicates)")

    # --- Compute Elo ratings ---
    print("\nComputing Elo ratings...")
    engine = EloEngine(settings)
    elo: dict[str, float] = {}
    last_match_date: dict[str, pd.Timestamp] = {}
    first_season = unified["Season"].iloc[0]

    rating_rows: list[tuple[int, int, str, float, float]] = []

    for i, (_, row) in enumerate(unified.iterrows()):
        match_id = match_ids[i]
        if match_id is None:
            continue

        home = row["HomeTeam"]
        away = row["AwayTeam"]
        result = row["FTR"]
        date = row["Date"]
        season = row["Season"]
        home_goals = int(row["FTHG"])
        away_goals = int(row["FTAG"])
        tier = int(row["Tier"])

        # Initialize new teams
        for team in (home, away):
            if team not in elo:
                init = settings.initial_elo if season == first_season else settings.promoted_elo
                elo[team] = init

        # Time decay
        engine.apply_time_decay(home, date, elo, last_match_date)
        engine.apply_time_decay(away, date, elo, last_match_date)

        # Update ratings
        new_h, new_a, dh, da = engine.elo_update(
            elo[home], elo[away], result, home_goals, away_goals, tier
        )
        elo[home] = new_h
        elo[away] = new_a
        last_match_date[home] = date
        last_match_date[away] = date

        date_str = pd.Timestamp(date).strftime("%Y-%m-%d")
        rating_rows.append((team_ids[home], match_id, date_str, new_h, dh))
        rating_rows.append((team_ids[away], match_id, date_str, new_a, da))

    # Bulk insert ratings
    print("Inserting ratings history...")
    conn.executemany(
        """INSERT INTO ratings_history (team_id, match_id, date, rating, rating_delta)
           VALUES (?, ?, ?, ?, ?)""",
        rating_rows,
    )
    conn.commit()
    print(f"  {len(rating_rows)} rating entries")

    # --- Record parameters ---
    insert_parameters(
        conn,
        k_factor=settings.k_factor,
        home_advantage=settings.home_advantage,
        decay_rate=settings.decay_rate,
        promoted_elo=settings.promoted_elo,
        spread=settings.spread,
        matches_processed=inserted,
    )
    conn.commit()

    # --- Verify ---
    print(f"\n{'=' * 60}")
    print("VERIFICATION")
    print(f"{'=' * 60}")
    print(f"  Teams:   {get_team_count(conn)}")
    print(f"  Matches: {get_match_count(conn)}")

    rh_count = conn.execute("SELECT COUNT(*) as cnt FROM ratings_history").fetchone()
    print(f"  Ratings: {rh_count['cnt']}")

    # Top 10
    print(f"\n  Top 10 teams:")
    top = conn.execute(
        """SELECT t.name, rh.rating
           FROM ratings_history rh
           JOIN teams t ON t.id = rh.team_id
           WHERE rh.id IN (
               SELECT rh2.id FROM ratings_history rh2
               WHERE rh2.team_id = rh.team_id
               ORDER BY rh2.date DESC, rh2.id DESC
               LIMIT 1
           )
           ORDER BY rh.rating DESC
           LIMIT 10"""
    ).fetchall()
    for i, row in enumerate(top, 1):
        print(f"    {i:2d}. {row['name']:<25} {row['rating']:.0f}")

    conn.close()
    print(f"\nDone. Database written to: {db_path or 'data/elo.db'}")


if __name__ == "__main__":
    seed_database()
