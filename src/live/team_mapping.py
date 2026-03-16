"""Team name matching between football-data.org and internal team names.

Maps external API team IDs and names to internal team IDs used in the Elo
database. Uses a combination of known mappings and fuzzy string matching
(stdlib difflib only, no extra dependencies).
"""

import sqlite3
import unicodedata
from difflib import SequenceMatcher

# football-data.org API name -> Football-Data.co.uk (internal) name.
# Only includes names that differ; identical names need no mapping.
FOOTBALL_DATA_ORG_NAMES: dict[str, str] = {
    # England (Premier League - PL)
    "Manchester United FC": "Man United",
    "Manchester City FC": "Man City",
    "Tottenham Hotspur FC": "Tottenham",
    "Newcastle United FC": "Newcastle",
    "Wolverhampton Wanderers FC": "Wolves",
    "West Ham United FC": "West Ham",
    "Brighton & Hove Albion FC": "Brighton",
    "Nottingham Forest FC": "Nott'm Forest",
    "AFC Bournemouth": "Bournemouth",
    "Arsenal FC": "Arsenal",
    "Aston Villa FC": "Aston Villa",
    "Chelsea FC": "Chelsea",
    "Liverpool FC": "Liverpool",
    "Leicester City FC": "Leicester",
    "Crystal Palace FC": "Crystal Palace",
    "Everton FC": "Everton",
    "Fulham FC": "Fulham",
    "Brentford FC": "Brentford",
    "Ipswich Town FC": "Ipswich",
    "Southampton FC": "Southampton",
    "Burnley FC": "Burnley",
    "Sheffield United FC": "Sheffield United",
    "Luton Town FC": "Luton",
    "West Bromwich Albion FC": "West Brom",
    "Leeds United FC": "Leeds",
    "Norwich City FC": "Norwich",
    "Watford FC": "Watford",
    "Queens Park Rangers FC": "QPR",
    "Stoke City FC": "Stoke",
    "Huddersfield Town AFC": "Huddersfield",
    "Swansea City AFC": "Swansea",
    "Cardiff City FC": "Cardiff",
    "Hull City AFC": "Hull",
    "Middlesbrough FC": "Middlesbrough",
    "Sunderland AFC": "Sunderland",
    "Wigan Athletic FC": "Wigan",
    "Reading FC": "Reading",
    "Bolton Wanderers FC": "Bolton",
    "Blackburn Rovers FC": "Blackburn",
    "Birmingham City FC": "Birmingham",
    "Blackpool FC": "Blackpool",
    # Spain (La Liga - PD)
    "Club Atlético de Madrid": "Ath Madrid",
    "Atlético de Madrid": "Ath Madrid",
    "Athletic Club": "Ath Bilbao",
    "FC Barcelona": "Barcelona",
    "Real Madrid CF": "Real Madrid",
    "Villarreal CF": "Villarreal",
    "Sevilla FC": "Sevilla",
    "Real Betis Balompié": "Betis",
    "Real Sociedad de Fútbol": "Sociedad",
    "Valencia CF": "Valencia",
    "RC Celta de Vigo": "Celta",
    "CA Osasuna": "Osasuna",
    "Getafe CF": "Getafe",
    "Girona FC": "Girona",
    "RCD Mallorca": "Mallorca",
    "UD Las Palmas": "Las Palmas",
    "Deportivo Alavés": "Alaves",
    "Rayo Vallecano de Madrid": "Vallecano",
    "RCD Espanyol de Barcelona": "Espanol",
    "CD Leganés": "Leganes",
    "Real Valladolid CF": "Valladolid",
    "Granada CF": "Granada",
    "SD Eibar": "Eibar",
    "Málaga CF": "Malaga",
    "UD Almería": "Almeria",
    "Elche CF": "Elche",
    "SD Huesca": "Huesca",
    "Cádiz CF": "Cadiz",
    "RC Deportivo La Coruña": "La Coruna",
    "Real Zaragoza": "Zaragoza",
    "Real Sporting de Gijón": "Sp Gijon",
    "Levante UD": "Levante",
    "Córdoba CF": "Cordoba",
    "Hércules CF": "Hercules",
    "Real Oviedo": "Oviedo",
    "Racing de Santander": "Santander",
    # Germany (Bundesliga - BL1)
    "FC Bayern München": "Bayern Munich",
    "Borussia Dortmund": "Dortmund",
    "Bayer 04 Leverkusen": "Leverkusen",
    "RB Leipzig": "RB Leipzig",
    "VfB Stuttgart": "Stuttgart",
    "Eintracht Frankfurt": "Ein Frankfurt",
    "VfL Wolfsburg": "Wolfsburg",
    "SC Freiburg": "Freiburg",
    "Borussia Mönchengladbach": "M'gladbach",
    "1. FC Union Berlin": "Union Berlin",
    "TSG 1899 Hoffenheim": "Hoffenheim",
    "1. FC Heidenheim 1846": "Heidenheim",
    "SV Werder Bremen": "Werder Bremen",
    "FC Augsburg": "Augsburg",
    "1. FSV Mainz 05": "Mainz",
    "SV Darmstadt 98": "Darmstadt",
    "1. FC Köln": "FC Koln",
    "Hertha BSC": "Hertha",
    "FC Schalke 04": "Schalke 04",
    "Arminia Bielefeld": "Bielefeld",
    "SpVgg Greuther Fürth": "Greuther Furth",
    "SC Paderborn 07": "Paderborn",
    "Fortuna Düsseldorf": "Fortuna Dusseldorf",
    "1. FC Nürnberg": "Nurnberg",
    "Hamburger SV": "Hamburg",
    "Hannover 96": "Hannover",
    "VfL Bochum 1848": "Bochum",
    "FC Ingolstadt 04": "Ingolstadt",
    "Eintracht Braunschweig": "Braunschweig",
    "1. FC Kaiserslautern": "Kaiserslautern",
    "FC St. Pauli": "St Pauli",
    "Holstein Kiel": "Holstein Kiel",
    # Italy (Serie A - SA)
    "AC Milan": "Milan",
    "FC Internazionale Milano": "Inter",
    "Juventus FC": "Juventus",
    "SSC Napoli": "Napoli",
    "AS Roma": "Roma",
    "SS Lazio": "Lazio",
    "ACF Fiorentina": "Fiorentina",
    "Atalanta BC": "Atalanta",
    "Bologna FC 1909": "Bologna",
    "Torino FC": "Torino",
    "Udinese Calcio": "Udinese",
    "US Sassuolo Calcio": "Sassuolo",
    "Genoa CFC": "Genoa",
    "Cagliari Calcio": "Cagliari",
    "Parma Calcio 1913": "Parma",
    "Hellas Verona FC": "Verona",
    "US Lecce": "Lecce",
    "Empoli FC": "Empoli",
    "Venezia FC": "Venezia",
    "US Salernitana 1919": "Salernitana",
    "Spezia Calcio": "Spezia",
    "US Cremonese": "Cremonese",
    "Benevento Calcio": "Benevento",
    "FC Crotone": "Crotone",
    "Brescia Calcio": "Brescia",
    "SPAL": "Spal",
    "Frosinone Calcio": "Frosinone",
    "AC Monza": "Monza",
    "Como 1907": "Como",
    "AC ChievoVerona": "Chievo",
    # France (Ligue 1 - FL1)
    "Paris Saint-Germain FC": "Paris SG",
    "Olympique de Marseille": "Marseille",
    "Olympique Lyonnais": "Lyon",
    "AS Monaco FC": "Monaco",
    "LOSC Lille": "Lille",
    "OGC Nice": "Nice",
    "RC Lens": "Lens",
    "Stade Rennais FC 1901": "Rennes",
    "Stade Brestois 29": "Brest",
    "RC Strasbourg Alsace": "Strasbourg",
    "Toulouse FC": "Toulouse",
    "FC Nantes": "Nantes",
    "Montpellier HSC": "Montpellier",
    "Stade de Reims": "Reims",
    "Le Havre AC": "Le Havre",
    "FC Metz": "Metz",
    "Clermont Foot 63": "Clermont",
    "FC Lorient": "Lorient",
    "Angers SCO": "Angers",
    "AJ Auxerre": "Auxerre",
    "AS Saint-Étienne": "St Etienne",
    "Dijon FCO": "Dijon",
    "Nîmes Olympique": "Nimes",
    "Amiens SC": "Amiens",
    "SM Caen": "Caen",
    "En Avant de Guingamp": "Guingamp",
    "Girondins de Bordeaux": "Bordeaux",
    "SC Bastia": "Bastia",
    "FC Sochaux-Montbéliard": "Sochaux",
    "Valenciennes FC": "Valenciennes",
    "ES Troyes AC": "Troyes",
    "Évian Thonon Gaillard FC": "Evian Thonon Gaillard",
    "AC Ajaccio": "Ajaccio",
    "GFC Ajaccio": "Ajaccio GFCO",
    "AS Nancy-Lorraine": "Nancy",
    "Paris FC": "Paris FC",
    "Racing Club de Lens": "Lens",
    # Champions League (CL) - non-top-5 teams
    "AFC Ajax": "Ajax",
    "PSV": "PSV",
    "Feyenoord Rotterdam": "Feyenoord",
    "FC Porto": "Porto",
    "SL Benfica": "Benfica",
    "Sporting CP": "Sporting CP",
    "Celtic FC": "Celtic",
    "Rangers FC": "Rangers",
    "Club Brugge KV": "Club Brugge",
    "FC Red Bull Salzburg": "RB Salzburg",
    "BSC Young Boys": "Young Boys",
    "FK Crvena Zvezda": "Crvena Zvezda",
    "FC Shakhtar Donetsk": "Shakhtar Donetsk",
    "GNK Dinamo Zagreb": "Dinamo Zagreb",
    "Galatasaray SK": "Galatasaray",
    "Fenerbahçe SK": "Fenerbahce",
    "Beşiktaş JK": "Besiktas",
    "Olympiacos FC": "Olympiakos",
    "PAOK FC": "PAOK",
    "FC Basel 1893": "Basel",
    "Ferencvárosi TC": "Ferencvaros",
    "SK Slavia Praha": "Slavia Praha",
    "AC Sparta Praha": "Sparta Praha",
    "SK Sturm Graz": "Sturm Graz",
    "Malmö FF": "Malmo",
    "FC Midtjylland": "Midtjylland",
    "FK Bodø/Glimt": "Bodo/Glimt",
    "Qarabağ FK": "Qarabag",
    "PFC Ludogorets 1945 Razgrad": "Ludogorets",
    "Sport Lisboa e Benfica": "Benfica",
}


def normalize_name(name: str) -> str:
    """Normalize a team name for fuzzy comparison.

    Lowercases, strips common suffixes (FC, AFC, SC, CF, etc.),
    removes accents/diacritics, and collapses whitespace.

    Args:
        name: Raw team name.

    Returns:
        Normalized name string for comparison purposes.
    """
    if not name:
        return ""

    # Remove diacritics (e.g. ö -> o, é -> e)
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_name = "".join(c for c in nfkd if not unicodedata.combining(c))

    # Lowercase
    result = ascii_name.lower().strip()

    # Remove common suffixes/prefixes
    suffixes = [" fc", " afc", " sc", " cf", " bc", " fk",
                " ssc", " ss", " us", " as", " ac", " rc",
                " calcio", " 1909", " 1913", " 1846", " 1848",
                " 1901", " 1945"]
    for suffix in suffixes:
        if result.endswith(suffix):
            result = result[: -len(suffix)].strip()

    prefixes = ["fc ", "ac ", "afc ", "sc ", "rc ", "us ", "ss ",
                "ssc ", "as ", "vfl ", "vfb ", "sv ", "spvgg ",
                "tsg ", "1. "]
    for prefix in prefixes:
        if result.startswith(prefix):
            result = result[len(prefix) :].strip()

    # Collapse whitespace
    result = " ".join(result.split())

    return result


def find_best_match(
    api_name: str,
    known_teams: list[str],
    threshold: float = 0.7,
) -> str | None:
    """Find the best fuzzy match for an API team name among known teams.

    Uses difflib.SequenceMatcher on normalized names. Returns the best
    match above the threshold, or None if no match is good enough.

    Args:
        api_name: Team name from the external API.
        known_teams: List of internal team names to match against.
        threshold: Minimum similarity ratio (0.0 to 1.0).

    Returns:
        Best matching internal team name, or None if below threshold.
    """
    normalized_api = normalize_name(api_name)
    best_score = 0.0
    best_match = None

    for team in known_teams:
        normalized_team = normalize_name(team)
        score = SequenceMatcher(None, normalized_api, normalized_team).ratio()
        if score > best_score:
            best_score = score
            best_match = team

    if best_score >= threshold:
        return best_match
    return None


def resolve_team(
    api_name: str,
    known_teams: list[str],
    threshold: float = 0.7,
) -> str | None:
    """Resolve an API team name to an internal team name.

    First checks the known mappings dict, then falls back to fuzzy matching.

    Args:
        api_name: Team name from football-data.org API.
        known_teams: List of all internal team names.
        threshold: Fuzzy match threshold.

    Returns:
        Internal team name, or None if no match found.
    """
    # 1) Check known mappings
    if api_name in FOOTBALL_DATA_ORG_NAMES:
        mapped = FOOTBALL_DATA_ORG_NAMES[api_name]
        if mapped in known_teams:
            return mapped

    # 2) Check if the name already matches exactly
    if api_name in known_teams:
        return api_name

    # 3) Fuzzy match
    return find_best_match(api_name, known_teams, threshold)


# --- Database operations (sync, matching repository.py patterns) ---


def get_mapping(
    conn: sqlite3.Connection,
    api_source: str,
    api_team_id: int,
) -> int | None:
    """Look up internal team_id from the mapping table.

    Args:
        conn: SQLite connection.
        api_source: API source identifier (e.g., 'football-data.org').
        api_team_id: Team ID in the external API.

    Returns:
        Internal team_id, or None if not mapped.
    """
    row = conn.execute(
        "SELECT team_id FROM api_team_mappings WHERE api_source = ? AND api_team_id = ?",
        (api_source, api_team_id),
    ).fetchone()
    if row is None:
        return None
    return row["team_id"] if isinstance(row, sqlite3.Row) else row[0]


def save_mapping(
    conn: sqlite3.Connection,
    api_source: str,
    api_team_id: int,
    api_team_name: str,
    team_id: int,
) -> None:
    """Insert or update a team mapping.

    Uses INSERT OR REPLACE to handle both new and existing mappings.

    Args:
        conn: SQLite connection.
        api_source: API source identifier.
        api_team_id: Team ID in the external API.
        api_team_name: Team name as returned by the API.
        team_id: Internal team ID.
    """
    conn.execute(
        """INSERT OR REPLACE INTO api_team_mappings
           (api_source, api_team_id, api_team_name, team_id)
           VALUES (?, ?, ?, ?)""",
        (api_source, api_team_id, api_team_name, team_id),
    )
    conn.commit()


def get_unmapped_teams(
    conn: sqlite3.Connection,
    api_source: str,
) -> list[dict]:
    """Find API teams that have been seen but have no internal mapping.

    This queries the api_team_mappings table for entries where the team_id
    does not correspond to a valid team in the teams table (unlikely with
    FK constraints), or more practically, finds API teams that were logged
    but couldn't be auto-matched.

    For the typical use case, this returns entries from a staging/log context.
    The main table enforces FK constraints, so unmapped teams are those
    that haven't been inserted yet.

    Args:
        conn: SQLite connection.
        api_source: API source identifier.

    Returns:
        List of dicts with api_team_id and api_team_name for unmapped teams.
    """
    rows = conn.execute(
        """SELECT atm.api_team_id, atm.api_team_name
           FROM api_team_mappings atm
           LEFT JOIN teams t ON t.id = atm.team_id
           WHERE atm.api_source = ? AND t.id IS NULL""",
        (api_source,),
    ).fetchall()

    return [
        {"api_team_id": row[0], "api_team_name": row[1]}
        for row in rows
    ]


def get_all_mappings(
    conn: sqlite3.Connection,
    api_source: str,
) -> list[dict]:
    """Get all team mappings for an API source.

    Args:
        conn: SQLite connection.
        api_source: API source identifier.

    Returns:
        List of dicts with api_team_id, api_team_name, team_id, and team_name.
    """
    rows = conn.execute(
        """SELECT atm.api_team_id, atm.api_team_name, atm.team_id, t.name as team_name
           FROM api_team_mappings atm
           JOIN teams t ON t.id = atm.team_id
           WHERE atm.api_source = ?
           ORDER BY t.name""",
        (api_source,),
    ).fetchall()

    return [
        {
            "api_team_id": row[0],
            "api_team_name": row[1],
            "team_id": row[2],
            "team_name": row[3],
        }
        for row in rows
    ]
