#!/usr/bin/env python
"""One-time script to build team mappings from football-data.org API.

Connects to the football-data.org API, fetches team lists for each
competition, and maps them to internal team IDs using known mappings
and fuzzy matching.

Requires:
    - FOOTBALL_DATA_API_KEY environment variable (or .env file)
    - data/elo.db with teams table populated

Usage:
    uv run python scripts/build_team_mappings.py
"""

import os
import sqlite3
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    import httpx
except ImportError:
    print("Error: httpx is required. Install with: uv add httpx")
    sys.exit(1)

from src.db.connection import init_db
from src.live.team_mapping import (
    FOOTBALL_DATA_ORG_NAMES,
    find_best_match,
    get_mapping,
    resolve_team,
    save_mapping,
)

# football-data.org competition codes
COMPETITIONS = {
    "PL": "Premier League",
    "PD": "La Liga",
    "BL1": "Bundesliga",
    "SA": "Serie A",
    "FL1": "Ligue 1",
    "CL": "Champions League",
}

API_SOURCE = "football-data.org"
BASE_URL = "https://api.football-data.org/v4"


def get_api_key() -> str | None:
    """Get API key from environment or .env file."""
    key = os.environ.get("FOOTBALL_DATA_API_KEY")
    if key:
        return key

    # Try .env file
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line.startswith("FOOTBALL_DATA_API_KEY="):
                return line.split("=", 1)[1].strip().strip("'\"")
    return None


def fetch_teams_for_competition(
    client: httpx.Client, competition: str
) -> list[dict]:
    """Fetch team list for a competition from football-data.org.

    Args:
        client: httpx client with auth headers.
        competition: Competition code (e.g., 'PL', 'BL1').

    Returns:
        List of dicts with 'id' and 'name' from the API.
    """
    url = f"{BASE_URL}/competitions/{competition}/teams"
    resp = client.get(url)
    resp.raise_for_status()
    data = resp.json()
    return [{"id": t["id"], "name": t["name"]} for t in data.get("teams", [])]


def build_mappings(db_path: str | None = None) -> None:
    """Build team mappings for all competitions.

    For each competition, fetches the team list from football-data.org
    and attempts to match each API team to an internal team using:
    1. Known mappings dictionary
    2. Fuzzy string matching

    Saves successful mappings to the database and reports unmatched teams.
    """
    api_key = get_api_key()
    if not api_key:
        print("=" * 60)
        print("FOOTBALL_DATA_API_KEY not found!")
        print()
        print("To use this script, set your API key:")
        print("  export FOOTBALL_DATA_API_KEY='your-key-here'")
        print()
        print("Or add it to .env in the project root:")
        print("  FOOTBALL_DATA_API_KEY=your-key-here")
        print()
        print("Get a free API key at: https://www.football-data.org/")
        print("=" * 60)
        sys.exit(1)

    # Initialize database (applies schema including api_team_mappings table)
    conn = init_db(db_path)

    # Ensure the api_team_mappings table exists
    migration_path = PROJECT_ROOT / "src" / "db" / "migrations" / "003_add_api_team_mappings.sql"
    if migration_path.exists():
        conn.executescript(migration_path.read_text())

    # Get all known internal team names
    rows = conn.execute("SELECT DISTINCT name FROM teams ORDER BY name").fetchall()
    known_teams = [row[0] for row in rows]
    print(f"Found {len(known_teams)} teams in database")
    print()

    headers = {"X-Auth-Token": api_key}
    client = httpx.Client(headers=headers, timeout=30.0)

    total_mapped = 0
    total_unmatched = 0
    all_unmatched: list[tuple[str, str]] = []  # (competition, api_name)

    try:
        for code, comp_name in COMPETITIONS.items():
            print(f"--- {comp_name} ({code}) ---")

            try:
                api_teams = fetch_teams_for_competition(client, code)
            except httpx.HTTPStatusError as e:
                print(f"  API error: {e.response.status_code} - {e.response.text[:200]}")
                continue
            except httpx.RequestError as e:
                print(f"  Request error: {e}")
                continue

            mapped = 0
            unmatched = 0

            for team in api_teams:
                api_id = team["id"]
                api_name = team["name"]

                # Check if already mapped
                existing = get_mapping(conn, API_SOURCE, api_id)
                if existing is not None:
                    mapped += 1
                    continue

                # Try to resolve
                internal_name = resolve_team(api_name, known_teams)
                if internal_name:
                    # Look up team_id
                    team_row = conn.execute(
                        "SELECT id FROM teams WHERE name = ?", (internal_name,)
                    ).fetchone()
                    if team_row:
                        team_id = team_row[0]
                        save_mapping(conn, API_SOURCE, api_id, api_name, team_id)
                        print(f"  Mapped: {api_name} -> {internal_name} (id={team_id})")
                        mapped += 1
                    else:
                        print(f"  WARN: Resolved to '{internal_name}' but not in DB")
                        unmatched += 1
                        all_unmatched.append((code, api_name))
                else:
                    print(f"  UNMATCHED: {api_name}")
                    unmatched += 1
                    all_unmatched.append((code, api_name))

            total_mapped += mapped
            total_unmatched += unmatched
            print(f"  Result: {mapped} mapped, {unmatched} unmatched")
            print()

    finally:
        client.close()

    # Summary
    print("=" * 60)
    print(f"TOTAL: {total_mapped} mapped, {total_unmatched} unmatched")
    print()

    if all_unmatched:
        print("Unmatched teams (need manual mapping):")
        for comp, name in sorted(all_unmatched):
            print(f"  [{comp}] {name}")
        print()
        print("Add these to FOOTBALL_DATA_ORG_NAMES in src/live/team_mapping.py")

    conn.close()


if __name__ == "__main__":
    build_mappings()
