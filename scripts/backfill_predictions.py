#!/usr/bin/env python3
"""Backfill predictions for historical matches.

Replays the Elo computation chronologically. Before each match (post
display_from_date), captures pre-match ratings, generates a prediction,
computes the Brier score against the actual result, and stores everything
in the predictions table with source='backfill'.

Idempotent: skips matches that already have a prediction.

Usage:
    uv run python scripts/backfill_predictions.py
"""

import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from src.config import EloSettings
from src.db.connection import get_db_path, init_db
from src.elo_engine import EloEngine
from src.live.prediction_tracker import compute_brier_score
from src.prediction import predict_match


def _get_all_matches(conn: sqlite3.Connection) -> pd.DataFrame:
    """Load all matches from the database ordered by date."""
    rows = conn.execute(
        """SELECT m.id, m.date, m.result, m.home_goals, m.away_goals,
                  m.season, c.tier,
                  th.name as home_team, ta.name as away_team
           FROM matches m
           JOIN teams th ON th.id = m.home_team_id
           JOIN teams ta ON ta.id = m.away_team_id
           JOIN competitions c ON c.id = m.competition_id
           ORDER BY m.date ASC, m.id ASC"""
    ).fetchall()

    return pd.DataFrame(
        [dict(row) for row in rows],
        columns=[
            "id", "date", "result", "home_goals", "away_goals",
            "season", "tier", "home_team", "away_team",
        ],
    )


def _get_existing_prediction_match_ids(conn: sqlite3.Connection) -> set[int]:
    """Get match IDs that already have predictions."""
    rows = conn.execute(
        "SELECT match_id FROM predictions WHERE match_id IS NOT NULL"
    ).fetchall()
    return {row["match_id"] for row in rows}


def backfill(db_path: str | Path | None = None) -> dict:
    """Run the backfill process.

    Args:
        db_path: Path to SQLite database. Defaults to data/elo.db.

    Returns:
        Summary dict with counts.
    """
    settings = EloSettings()
    engine = EloEngine(settings)
    display_from = settings.display_from_date

    conn = init_db(db_path)
    try:
        matches_df = _get_all_matches(conn)
        existing = _get_existing_prediction_match_ids(conn)

        # State for the Elo replay
        elo: dict[str, float] = {}
        last_match_date: dict[str, pd.Timestamp] = {}
        first_season = matches_df["season"].iloc[0] if len(matches_df) > 0 else None

        predictions_created = 0
        predictions_skipped = 0
        errors = 0
        now = datetime.now(timezone.utc).isoformat()
        batch_size = 1000
        batch_count = 0

        for _, row in matches_df.iterrows():
            match_id = row["id"]
            home = row["home_team"]
            away = row["away_team"]
            result = row["result"]
            date = pd.Timestamp(row["date"])
            season = row["season"]
            home_goals = int(row["home_goals"])
            away_goals = int(row["away_goals"])
            tier = int(row["tier"]) if row["tier"] else 5

            # Initialize new teams
            for team in (home, away):
                if team not in elo:
                    init_rating = (
                        settings.initial_elo
                        if season == first_season
                        else settings.promoted_elo
                    )
                    elo[team] = init_rating

            # Apply time decay (same as EloEngine.compute_ratings)
            engine.apply_time_decay(home, date, elo, last_match_date)
            engine.apply_time_decay(away, date, elo, last_match_date)

            # Capture pre-match ratings and generate prediction
            # (only for matches in the display window)
            if row["date"] >= display_from and match_id not in existing:
                try:
                    ratings_snapshot = {home: elo[home], away: elo[away]}
                    pred = predict_match(home, away, ratings_snapshot)

                    brier = compute_brier_score(
                        pred["p_home"], pred["p_draw"], pred["p_away"], result
                    )

                    conn.execute(
                        """INSERT INTO predictions
                           (match_id, p_home, p_draw, p_away,
                            home_elo, away_elo, brier_score, scored_at, source)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'backfill')""",
                        (
                            match_id,
                            pred["p_home"],
                            pred["p_draw"],
                            pred["p_away"],
                            pred["home_rating"],
                            pred["away_rating"],
                            brier,
                            now,
                        ),
                    )
                    predictions_created += 1
                    batch_count += 1

                    if batch_count >= batch_size:
                        conn.commit()
                        batch_count = 0
                except Exception as e:
                    errors += 1
                    if errors <= 5:
                        print(f"  Error on match {match_id} ({home} vs {away}): {e}")
            elif match_id in existing:
                predictions_skipped += 1

            # Update ratings (always, to keep state accurate)
            new_h, new_a, _, _ = engine.elo_update(
                elo[home], elo[away], result, home_goals, away_goals, tier
            )
            elo[home] = new_h
            elo[away] = new_a
            last_match_date[home] = date
            last_match_date[away] = date

        # Final commit
        conn.commit()

        return {
            "total_matches": len(matches_df),
            "predictions_created": predictions_created,
            "predictions_skipped": predictions_skipped,
            "errors": errors,
        }
    finally:
        conn.close()


def main() -> int:
    """CLI entry point."""
    print("=" * 60)
    print("PREDICTION BACKFILL")
    print("=" * 60)

    start = time.time()
    summary = backfill()
    elapsed = time.time() - start

    print(f"\nTotal matches:         {summary['total_matches']}")
    print(f"Predictions created:   {summary['predictions_created']}")
    print(f"Predictions skipped:   {summary['predictions_skipped']}")
    print(f"Errors:                {summary['errors']}")
    print(f"Elapsed:               {elapsed:.1f}s")
    print(f"\n{'=' * 60}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
