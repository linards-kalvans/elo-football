#!/usr/bin/env python3
"""Lightweight cron-style scheduler for daily Elo updates.

Runs run_daily_update() at 06:00 and 18:00 UTC. Checks every 5 minutes.
No external dependencies — uses only the Python standard library.

Usage:
    python scripts/cron_runner.py
"""

import asyncio
import logging
import time
from datetime import datetime, timezone

from src.live.ingestion import run_daily_update

logger = logging.getLogger("cron_runner")

SCHEDULE_HOURS = {6, 18}
CHECK_INTERVAL_SECONDS = 5 * 60  # 5 minutes


def _should_run(now: datetime, last_run_hour: int | None) -> bool:
    """Return True if current hour is a scheduled hour and hasn't run yet."""
    return now.hour in SCHEDULE_HOURS and now.hour != last_run_hour


def _execute_update() -> None:
    """Run the daily update, logging outcome."""
    logger.info("Starting daily update")
    try:
        summary = asyncio.run(run_daily_update())
        matches = summary.get("matches", {})
        fixtures = summary.get("fixtures", {})
        logger.info(
            "Daily update complete — %d matches ingested, %d predictions made",
            matches.get("matches_ingested", 0),
            fixtures.get("predictions_generated", 0),
        )
    except Exception:
        logger.exception("Daily update failed")


def main() -> None:
    """Main scheduler loop."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    logger.info(
        "Cron runner started — scheduled hours (UTC): %s, check interval: %ds",
        sorted(SCHEDULE_HOURS),
        CHECK_INTERVAL_SECONDS,
    )

    last_run_hour: int | None = None

    while True:
        now = datetime.now(timezone.utc)

        if _should_run(now, last_run_hour):
            _execute_update()
            last_run_hour = now.hour

        # Reset tracker when hour changes away from a schedule hour
        if now.hour not in SCHEDULE_HOURS:
            last_run_hour = None

        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
