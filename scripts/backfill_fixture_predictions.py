#!/usr/bin/env python3
"""Backfill missing predictions for upcoming fixtures.

Finds scheduled fixtures that have no prediction row and generates one using
the current Elo ratings. Safe to run repeatedly — skips fixtures that already
have a prediction.

Usage:
    uv run python scripts/backfill_fixture_predictions.py [--db PATH]
"""

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.connection import get_db_path
from src.db.repository import get_latest_match_date, get_ratings_at_date, insert_prediction
from src.prediction import predict_match


def backfill(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    latest_date = get_latest_match_date(conn)
    if not latest_date:
        print("No matches in database — cannot compute ratings.")
        conn.close()
        sys.exit(1)

    ratings = get_ratings_at_date(conn, latest_date)
    print(f"Ratings loaded as of {latest_date} ({len(ratings)} teams)")

    rows = conn.execute("""
        SELECT f.id, f.date, th.name AS home_name, ta.name AS away_name
        FROM fixtures f
        JOIN teams th ON th.id = f.home_team_id
        JOIN teams ta ON ta.id = f.away_team_id
        LEFT JOIN predictions p ON p.fixture_id = f.id
        WHERE f.status = 'scheduled'
          AND f.date >= date('now')
          AND p.id IS NULL
        ORDER BY f.date
    """).fetchall()

    print(f"Fixtures without predictions: {len(rows)}")
    if not rows:
        conn.close()
        return

    generated = 0
    skipped = []
    for row in rows:
        home, away = row["home_name"], row["away_name"]
        if home in ratings and away in ratings:
            pred = predict_match(home, away, ratings)
            insert_prediction(
                conn,
                p_home=pred["p_home"],
                p_draw=pred["p_draw"],
                p_away=pred["p_away"],
                home_elo=pred["home_rating"],
                away_elo=pred["away_rating"],
                fixture_id=row["id"],
            )
            generated += 1
        else:
            missing = [t for t in (home, away) if t not in ratings]
            skipped.append(f"  {row['date']}  {home} vs {away}  (no rating: {', '.join(missing)})")

    conn.commit()
    conn.close()

    print(f"Predictions generated: {generated}")
    if skipped:
        print(f"Skipped ({len(skipped)} — teams not in ratings):")
        for line in skipped:
            print(line)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=None, help="Path to elo.db")
    args = parser.parse_args()

    db_path = args.db or get_db_path()
    print(f"Database: {db_path}")
    backfill(db_path)


if __name__ == "__main__":
    main()
