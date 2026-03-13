#!/usr/bin/env python3
"""Data refresh pipeline: fetch, validate, ingest, rate, persist.

Idempotent — UNIQUE constraint on matches prevents duplicates.
Designed to be run via cron or manually.

Usage:
    uv run python src/pipeline.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from src.config import EloSettings
from src.data_loader import LEAGUE_CONFIG, load_all_leagues
from src.db.connection import get_db_path, init_db
from src.db.repository import (
    get_latest_match_date,
    get_match_count,
    get_team_count,
    insert_competition,
    insert_match,
    insert_parameters,
    insert_team,
)
from src.db.validation import validate_database
from src.elo_engine import EloEngine
from src.european_data import COMPETITION_FILES, STAGE_TIER, load_european_data


def run_pipeline(db_path: str | Path | None = None,
                 skip_validation: bool = False) -> dict:
    """Run the full data refresh pipeline.

    Steps:
        1. Load current data from CSVs/openfootball
        2. Determine new matches since last run
        3. Insert new matches
        4. Recompute all ratings (full recompute for consistency)
        5. Persist updated ratings
        6. Validate

    Args:
        db_path: Path to SQLite database. Defaults to data/elo.db.
        skip_validation: Skip validation step.

    Returns:
        Summary dict with counts.
    """
    print("=" * 60)
    print("ELO DATA REFRESH PIPELINE")
    print("=" * 60)

    resolved_path = get_db_path(db_path)
    is_fresh = not resolved_path.exists()

    if is_fresh:
        print("\nNo existing database found. Running initial seed...")
        from src.db.seed import seed_database
        seed_database(db_path)
        conn = init_db(db_path)
    else:
        conn = init_db(db_path)
        print(f"\nExisting database: {resolved_path}")
        print(f"  Current matches: {get_match_count(conn)}")
        print(f"  Current teams:   {get_team_count(conn)}")
        print(f"  Latest match:    {get_latest_match_date(conn)}")

    # --- Load fresh data ---
    print("\nLoading latest match data...")
    all_leagues = load_all_leagues(verbose=False)
    domestic_dfs = []
    for _, df in all_leagues.items():
        df = df.copy()
        df["Tier"] = 5
        df["Competition"] = df["League"]
        domestic_dfs.append(df)
    domestic = pd.concat(domestic_dfs, ignore_index=True)

    european = load_european_data(verbose=False)
    if not european.empty:
        european["League"] = european["Competition"]

    shared_cols = ["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR",
                   "Season", "League", "Competition", "Tier"]
    parts = [domestic[shared_cols]]
    if not european.empty:
        parts.append(european[shared_cols])
    unified = pd.concat(parts, ignore_index=True)
    unified = unified.sort_values("Date").reset_index(drop=True)

    print(f"  Total matches in source data: {len(unified)}")

    # --- Ensure all teams and competitions exist ---
    comp_ids: dict[str, int] = {}
    for config in LEAGUE_CONFIG.values():
        comp_ids[config["name"]] = insert_competition(
            conn, config["name"], tier=5, country=config["country"]
        )

    eu_tiers: dict[str, int] = {}
    for (comp_key, _), tier in STAGE_TIER.items():
        comp_name = COMPETITION_FILES[comp_key]
        if comp_name not in eu_tiers or tier < eu_tiers[comp_name]:
            eu_tiers[comp_name] = tier
    for comp_name, tier in eu_tiers.items():
        comp_ids[comp_name] = insert_competition(
            conn, comp_name, tier=tier, country="Europe"
        )

    # Determine team countries
    team_countries: dict[str, str] = {}
    for config in LEAGUE_CONFIG.values():
        mask = unified["Competition"] == config["name"]
        for team in pd.concat([
            unified.loc[mask, "HomeTeam"],
            unified.loc[mask, "AwayTeam"],
        ]).unique():
            team_countries[team] = config["country"]

    all_teams = set(unified["HomeTeam"].unique()) | set(unified["AwayTeam"].unique())
    team_ids: dict[str, int] = {}
    for name in sorted(all_teams):
        team_ids[name] = insert_team(conn, name, country=team_countries.get(name, ""))
    conn.commit()

    # --- Insert new matches ---
    print("\nInserting new matches...")
    new_matches = 0
    duplicates = 0
    match_ids: list[int | None] = []

    for _, row in unified.iterrows():
        comp_id = comp_ids.get(row["Competition"])
        if comp_id is None:
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
            new_matches += 1
        else:
            duplicates += 1

    conn.commit()
    print(f"  New matches: {new_matches}")
    print(f"  Duplicates skipped: {duplicates}")

    if new_matches > 0:
        # --- Full recompute of ratings ---
        print("\nRecomputing all Elo ratings...")
        conn.execute("DELETE FROM ratings_history")
        conn.commit()

        # Reload match IDs in order
        all_match_rows = conn.execute(
            """SELECT m.id, m.date, m.home_team_id, m.away_team_id,
                      m.home_goals, m.away_goals, m.result, m.season,
                      c.tier,
                      th.name as home_name, ta.name as away_name
               FROM matches m
               JOIN competitions c ON c.id = m.competition_id
               JOIN teams th ON th.id = m.home_team_id
               JOIN teams ta ON ta.id = m.away_team_id
               ORDER BY m.date ASC, m.id ASC"""
        ).fetchall()

        settings = EloSettings()
        engine = EloEngine(settings)
        elo: dict[str, float] = {}
        last_match_date: dict[str, pd.Timestamp] = {}
        rating_rows: list[tuple[int, int, str, float, float]] = []

        # Determine first season
        first_season = all_match_rows[0]["season"] if all_match_rows else ""

        for mrow in all_match_rows:
            home = mrow["home_name"]
            away = mrow["away_name"]
            date = pd.Timestamp(mrow["date"])
            season = mrow["season"]
            tier = mrow["tier"]

            for team in (home, away):
                if team not in elo:
                    init = (settings.initial_elo if season == first_season
                            else settings.promoted_elo)
                    elo[team] = init

            engine.apply_time_decay(home, date, elo, last_match_date)
            engine.apply_time_decay(away, date, elo, last_match_date)

            new_h, new_a, dh, da = engine.elo_update(
                elo[home], elo[away], mrow["result"],
                mrow["home_goals"], mrow["away_goals"], tier
            )
            elo[home] = new_h
            elo[away] = new_a
            last_match_date[home] = date
            last_match_date[away] = date

            date_str = mrow["date"]
            rating_rows.append((mrow["home_team_id"], mrow["id"], date_str, new_h, dh))
            rating_rows.append((mrow["away_team_id"], mrow["id"], date_str, new_a, da))

        conn.executemany(
            """INSERT INTO ratings_history
               (team_id, match_id, date, rating, rating_delta)
               VALUES (?, ?, ?, ?, ?)""",
            rating_rows,
        )

        insert_parameters(
            conn,
            k_factor=settings.k_factor,
            home_advantage=settings.home_advantage,
            decay_rate=settings.decay_rate,
            promoted_elo=settings.promoted_elo,
            spread=settings.spread,
            matches_processed=len(all_match_rows),
        )
        conn.commit()
        print(f"  {len(rating_rows)} rating entries written")
    else:
        print("\nNo new matches — ratings unchanged.")

    # --- Validation ---
    if not skip_validation:
        print("\nRunning validation...")
        issues = validate_database(conn)
        if issues:
            print(f"  WARNING: {len(issues)} validation issue(s):")
            for issue in issues:
                print(f"    - {issue}")
        else:
            print("  All checks passed.")

    # --- Summary ---
    summary = {
        "new_matches": new_matches,
        "duplicates": duplicates,
        "total_matches": get_match_count(conn),
        "total_teams": get_team_count(conn),
        "latest_date": get_latest_match_date(conn),
    }

    print(f"\n{'=' * 60}")
    print("PIPELINE COMPLETE")
    print(f"{'=' * 60}")
    for k, v in summary.items():
        print(f"  {k}: {v}")

    conn.close()
    return summary


if __name__ == "__main__":
    run_pipeline()
