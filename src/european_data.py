"""Parser and loader for openfootball European competition data.

Parses the football.txt format used by github.com/openfootball/champions-league
into DataFrames with the same schema as domestic league data, plus competition
metadata (competition name, stage, tier).
"""

import re
from pathlib import Path
from typing import Optional

import pandas as pd

from src.team_names import normalize_team_name


# Competition file mapping
COMPETITION_FILES = {
    "cl": "Champions League",
    "el": "Europa League",
    "conf": "Conference League",
}

# Stage-to-tier mapping for K multipliers
# Tier 1: CL knockout (Round of 16+), Tier 2: CL group/league phase,
# Tier 3: EL knockout, Tier 4: EL group + Conference League, Tier 5: domestic
STAGE_TIER = {
    # CL stages
    ("cl", "knockout"): 1,
    ("cl", "group"): 2,
    ("cl", "league"): 2,
    ("cl", "playoffs"): 2,
    # EL stages
    ("el", "knockout"): 3,
    ("el", "group"): 4,
    ("el", "league"): 4,
    ("el", "playoffs"): 4,
    # Conference League
    ("conf", "knockout"): 4,
    ("conf", "group"): 4,
    ("conf", "league"): 4,
    ("conf", "playoffs"): 4,
}

# Regex patterns
DATE_FULL_RE = re.compile(
    r"^\s+(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+"
    r"(\w+)/(\d+)\s+(\d{4})"
)
DATE_CONT_RE = re.compile(
    r"^\s+(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+"
    r"(\w+)/(\d+)\s*$"
)
MATCH_RE = re.compile(
    r"^\s+(?:\d{1,2}\.\d{2}\s+)?"  # optional time
    r"(.+?)\s+v\s+(.+?)\s+"        # team1 v team2
    r"(\d+)-(\d+)"                  # full-time score
    r"(?:\s+pen\.\s+(\d+)-(\d+))?"  # optional penalty score
    r"(?:\s+a\.e\.t\.)?"            # optional extra time marker
    r"(?:\s+\(.*\))?"               # optional halftime/extra time detail
    r"\s*$"
)
# Some lines have pen before the FT score: "4-3 pen. 1-0 a.e.t."
MATCH_PEN_RE = re.compile(
    r"^\s+(?:\d{1,2}\.\d{2}\s+)?"
    r"(.+?)\s+v\s+(.+?)\s+"
    r"(\d+)-(\d+)\s+pen\.\s+"      # penalty score first
    r"(\d+)-(\d+)"                  # then FT/AET score
    r"(?:\s+a\.e\.t\.)?"
    r"(?:\s+\(.*\))?"
    r"\s*$"
)
SECTION_RE = re.compile(r"^»\s+(.+)$")

MONTH_MAP = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}


def _parse_team_name(raw: str) -> tuple[str, str]:
    """Extract team name and country code from 'Team Name (CODE)'.

    Returns:
        (team_name, country_code)
    """
    raw = raw.strip()
    m = re.match(r"^(.+?)\s*\((\w{3})\)\s*$", raw)
    if m:
        return m.group(1).strip(), m.group(2)
    return raw, ""


def _classify_stage(section: str) -> str:
    """Classify a section header into stage type: group, league, playoffs, knockout."""
    s = section.lower()
    if any(kw in s for kw in ["group"]):
        return "group"
    if any(kw in s for kw in ["league", "matchday"]):
        # New CL format uses "League, Matchday N"
        if "playoffs" in s:
            return "playoffs"
        return "league"
    if any(kw in s for kw in ["playoff"]):
        return "playoffs"
    if any(kw in s for kw in [
        "round of", "quarterfinal", "semifinal", "final",
        "1st round", "2nd round", "3rd round",
    ]):
        return "knockout"
    # Default to group for unrecognized sections
    return "group"


def parse_competition_file(filepath: Path, comp_key: str, season: str) -> list[dict]:
    """Parse a single openfootball .txt file into match records.

    Args:
        filepath: Path to the .txt file.
        comp_key: Competition key (cl, el, conf).
        season: Season string (e.g., '2024-25').

    Returns:
        List of match dicts with keys: Date, HomeTeam, AwayTeam, HomeCountry,
        AwayCountry, FTHG, FTAG, FTR, Season, Competition, Stage, Tier.
    """
    matches = []
    current_year = None
    current_month = None
    current_day = None
    current_section = ""
    current_stage = "group"

    text = filepath.read_text(encoding="utf-8")
    for line in text.splitlines():
        # Skip empty lines, comments, header lines
        if not line.strip() or line.startswith("=") or line.startswith("#"):
            continue

        # Section header
        sec_m = SECTION_RE.match(line)
        if sec_m:
            current_section = sec_m.group(1)
            current_stage = _classify_stage(current_section)
            continue

        # Full date line: "Tue Sep/17 2024"
        date_m = DATE_FULL_RE.match(line)
        if date_m:
            month_str, day_str, year_str = date_m.groups()
            current_month = MONTH_MAP.get(month_str)
            current_day = int(day_str)
            current_year = int(year_str)
            continue

        # Continuation date line: "Wed Sep/18"
        date_c = DATE_CONT_RE.match(line)
        if date_c:
            month_str, day_str = date_c.groups()
            new_month = MONTH_MAP.get(month_str)
            new_day = int(day_str)
            if current_year is not None:
                # Handle year rollover: only Dec->Jan transition
                if current_month == 12 and new_month == 1:
                    current_year += 1
                current_month = new_month
                current_day = new_day
            continue

        # Try penalty-first format: "4-3 pen. 1-0 a.e.t."
        pen_m = MATCH_PEN_RE.match(line)
        if pen_m:
            team1_raw, team2_raw = pen_m.group(1), pen_m.group(2)
            # Groups 3-4 are penalty score, 5-6 are FT/AET score
            ft_home, ft_away = int(pen_m.group(5)), int(pen_m.group(6))
            team1, country1 = _parse_team_name(team1_raw)
            team2, country2 = _parse_team_name(team2_raw)

            if ft_home > ft_away:
                ftr = "H"
            elif ft_away > ft_home:
                ftr = "A"
            else:
                ftr = "D"  # AET ended in draw, decided by penalties

            if current_year and current_month and current_day:
                tier = STAGE_TIER.get((comp_key, current_stage), 4)
                matches.append({
                    "Date": pd.Timestamp(current_year, current_month, current_day),
                    "HomeTeam": team1,
                    "AwayTeam": team2,
                    "HomeCountry": country1,
                    "AwayCountry": country2,
                    "FTHG": ft_home,
                    "FTAG": ft_away,
                    "FTR": ftr,
                    "Season": season,
                    "Competition": COMPETITION_FILES[comp_key],
                    "Stage": current_section,
                    "Tier": tier,
                })
            continue

        # Standard match line
        match_m = MATCH_RE.match(line)
        if match_m:
            team1_raw, team2_raw = match_m.group(1), match_m.group(2)
            ft_home, ft_away = int(match_m.group(3)), int(match_m.group(4))
            team1, country1 = _parse_team_name(team1_raw)
            team2, country2 = _parse_team_name(team2_raw)

            if ft_home > ft_away:
                ftr = "H"
            elif ft_away > ft_home:
                ftr = "A"
            else:
                ftr = "D"

            if current_year and current_month and current_day:
                tier = STAGE_TIER.get((comp_key, current_stage), 4)
                matches.append({
                    "Date": pd.Timestamp(current_year, current_month, current_day),
                    "HomeTeam": team1,
                    "AwayTeam": team2,
                    "HomeCountry": country1,
                    "AwayCountry": country2,
                    "FTHG": ft_home,
                    "FTAG": ft_away,
                    "FTR": ftr,
                    "Season": season,
                    "Competition": COMPETITION_FILES[comp_key],
                    "Stage": current_section,
                    "Tier": tier,
                })
            continue

    return matches


def load_european_data(
    data_dir: str = "data/european",
    competitions: Optional[list[str]] = None,
    seasons: Optional[list[str]] = None,
    verbose: bool = True,
) -> pd.DataFrame:
    """Load all European competition data from openfootball text files.

    Args:
        data_dir: Directory containing season subdirectories with .txt files.
        competitions: List of competition keys to load (cl, el, conf).
            If None, loads all available.
        seasons: List of season strings to load (e.g., ['2023-24']).
            If None, loads all available.
        verbose: Print summary statistics.

    Returns:
        DataFrame with columns: Date, HomeTeam, AwayTeam, HomeCountry,
        AwayCountry, FTHG, FTAG, FTR, Season, Competition, Stage, Tier.
    """
    base = Path(data_dir)
    if not base.exists():
        if verbose:
            print(f"Warning: European data directory not found: {base}")
        return pd.DataFrame()

    if competitions is None:
        competitions = list(COMPETITION_FILES.keys())

    all_matches = []
    season_dirs = sorted([d for d in base.iterdir() if d.is_dir()])
    if seasons is not None:
        season_dirs = [d for d in season_dirs if d.name in seasons]

    for season_dir in season_dirs:
        season = season_dir.name
        for comp_key in competitions:
            filepath = season_dir / f"{comp_key}.txt"
            if not filepath.exists():
                continue
            try:
                matches = parse_competition_file(filepath, comp_key, season)
                all_matches.extend(matches)
                if verbose:
                    print(f"  {season}/{comp_key}: {len(matches)} matches")
            except Exception as e:
                if verbose:
                    print(f"  Error parsing {filepath}: {e}")

    if not all_matches:
        if verbose:
            print("No European competition data loaded.")
        return pd.DataFrame()

    df = pd.DataFrame(all_matches)

    # Normalize team names to match domestic data conventions
    df["HomeTeam"] = df["HomeTeam"].map(normalize_team_name)
    df["AwayTeam"] = df["AwayTeam"].map(normalize_team_name)

    df = df.sort_values("Date").reset_index(drop=True)

    if verbose:
        print(f"\nEuropean competition data loaded:")
        print(f"  Total matches: {len(df)}")
        print(f"  Competitions: {df['Competition'].unique().tolist()}")
        print(f"  Seasons: {df['Season'].nunique()}")
        print(f"  Date range: {df['Date'].min().date()} to {df['Date'].max().date()}")
        for comp in df["Competition"].unique():
            comp_df = df[df["Competition"] == comp]
            print(f"  {comp}: {len(comp_df)} matches, "
                  f"{comp_df['Season'].nunique()} seasons")

    return df
