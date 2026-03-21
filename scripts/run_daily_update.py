#!/usr/bin/env python3
"""CLI script to run the daily live data update.

Fetches recent completed matches and upcoming fixtures from
football-data.org, ingests into the database, and recomputes ratings.

Usage:
    uv run python scripts/run_daily_update.py
"""

import asyncio
import logging
import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.live.ingestion import run_daily_update


def main() -> int:
    """Run the daily update and print summary."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    try:
        summary = asyncio.run(run_daily_update())
    except Exception:
        logging.exception("Daily update failed")
        return 1

    print("\n" + "=" * 60)
    print("DAILY UPDATE SUMMARY")
    print("=" * 60)

    matches = summary.get("matches", {})
    print("\nMatches:")
    print(f"  Competitions checked: {matches.get('competitions_checked', 0)}")
    print(f"  Matches fetched:     {matches.get('matches_fetched', 0)}")
    print(f"  Matches ingested:    {matches.get('matches_ingested', 0)}")
    print(f"  Matches skipped:     {matches.get('matches_skipped', 0)}")

    scoring = summary.get("scoring", {})
    print("\nPrediction Scoring:")
    print(f"  Predictions scored:  {scoring.get('scored_count', 0)}")
    print(f"  Scoring errors:      {scoring.get('errors', 0)}")

    fixtures = summary.get("fixtures", {})
    print("\nFixtures:")
    print(f"  Fixtures fetched:    {fixtures.get('fixtures_fetched', 0)}")
    print(f"  Fixtures ingested:   {fixtures.get('fixtures_ingested', 0)}")
    print(f"  Fixtures skipped:    {fixtures.get('fixtures_skipped', 0)}")
    print(f"  Predictions made:    {fixtures.get('predictions_generated', 0)}")

    print(f"\n{'=' * 60}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
