"""URL slug utilities and context resolution for the EloKit unified layout.

Converts entity names (countries, competitions, teams) to URL-safe slugs
and resolves URL paths back to database entities via cached lookup tables.
"""

import re
import unicodedata
from dataclasses import dataclass, field

from src.db.connection import get_async_connection


def to_slug(name: str) -> str:
    """Convert a name to a URL-safe slug.

    Handles unicode characters, accents, and special punctuation. The output
    is lowercase, hyphen-separated, with no leading/trailing hyphens.

    Args:
        name: The name to slugify (e.g., "Premier League", "Borussia
            Mönchengladbach", "1. FC Slovácko").

    Returns:
        URL-safe slug string (e.g., "premier-league",
        "borussia-monchengladbach", "1-fc-slovacko").
    """
    # Normalize unicode: decompose accented characters, then strip combining marks
    normalized = unicodedata.normalize("NFKD", name)
    ascii_text = "".join(
        c for c in normalized if not unicodedata.combining(c)
    )
    # Lowercase
    slug = ascii_text.lower()
    # Replace any non-alphanumeric character (except hyphen) with a hyphen
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    # Strip leading/trailing hyphens
    slug = slug.strip("-")
    return slug


# Country name mapping: slug -> display name
# Only the 5 domestic league countries + "Europe" for CL/EL/Conference
COUNTRY_SLUGS: dict[str, str] = {
    "england": "England",
    "spain": "Spain",
    "germany": "Germany",
    "italy": "Italy",
    "france": "France",
    "europe": "Europe",
}


COUNTRY_FLAG_URLS: dict[str, str] = {
    "England": "/static/flags/england.svg",
    "Spain": "/static/flags/spain.svg",
    "Germany": "/static/flags/germany.svg",
    "Italy": "/static/flags/italy.svg",
    "France": "/static/flags/france.svg",
    "Europe": "/static/flags/europe.svg",
}

COMPETITION_LOGO_URLS: dict[str, str] = {
    "Premier League": "/static/logos/competitions/premier-league.svg",
    "La Liga": "/static/logos/competitions/la-liga.svg",
    "Bundesliga": "/static/logos/competitions/bundesliga.svg",
    "Serie A": "/static/logos/competitions/serie-a.svg",
    "Ligue 1": "/static/logos/competitions/ligue-1.svg",
    "Champions League": "/static/logos/competitions/champions-league.svg",
    "Europa League": "/static/logos/competitions/europa-league.svg",
    "Conference League": "/static/logos/competitions/conference-league.svg",
}


@dataclass
class PageContext:
    """Resolved page context from a URL path.

    Attributes:
        level: One of "global", "nation", "league", "team".
        country: Country display name (e.g., "England"), or None for global.
        competition: Competition display name (e.g., "Premier League"),
            or None for global/nation levels.
        competition_id: Database competition ID, or None.
        team_id: Database team ID, or None.
        team_name: Team display name (e.g., "Liverpool"), or None.
    """

    level: str
    country: str | None = None
    competition: str | None = None
    competition_id: int | None = None
    team_id: int | None = None
    team_name: str | None = None


@dataclass
class SlugCache:
    """In-memory cache mapping slugs to database entities.

    Built once on application startup from the database. Provides O(1)
    lookups for URL path resolution.

    Attributes:
        competition_by_country_slug: Nested dict mapping
            country_slug -> competition_slug -> (competition_id, competition_name).
        team_by_competition_slug: Nested dict mapping
            competition_id -> team_slug -> (team_id, team_name).
        team_country: Mapping of team_id -> country string.
        country_competitions: Mapping of country_slug -> list of competition
            slugs (for validation).
    """

    competition_by_country_slug: dict[str, dict[str, tuple[int, str]]] = field(
        default_factory=dict
    )
    team_by_competition_slug: dict[int, dict[str, tuple[int, str]]] = field(
        default_factory=dict
    )
    team_country: dict[int, str] = field(default_factory=dict)
    country_competitions: dict[str, list[str]] = field(default_factory=dict)


# Module-level cache instance, populated via build_slug_cache()
_cache: SlugCache | None = None


async def build_slug_cache() -> SlugCache:
    """Build the slug lookup cache by querying all entities from the database.

    Queries all competitions, teams, and their relationships to build
    bidirectional slug-to-entity mappings.

    Returns:
        Populated SlugCache instance.
    """
    global _cache

    cache = SlugCache()
    conn = await get_async_connection()

    try:
        # Load competitions: map country_slug -> comp_slug -> (id, name)
        cursor = await conn.execute(
            "SELECT id, name, country FROM competitions ORDER BY name"
        )
        competitions = await cursor.fetchall()

        for row in competitions:
            comp_id, comp_name, comp_country = row[0], row[1], row[2]
            country_slug = to_slug(comp_country)
            comp_slug = to_slug(comp_name)

            if country_slug not in cache.competition_by_country_slug:
                cache.competition_by_country_slug[country_slug] = {}
            cache.competition_by_country_slug[country_slug][comp_slug] = (
                comp_id,
                comp_name,
            )

            if country_slug not in cache.country_competitions:
                cache.country_competitions[country_slug] = []
            cache.country_competitions[country_slug].append(comp_slug)

            # Initialize team dict for this competition
            if comp_id not in cache.team_by_competition_slug:
                cache.team_by_competition_slug[comp_id] = {}

        # Load teams and map them to their domestic competition.
        # Teams with a country are in a domestic league; teams without a
        # country (European-only) are mapped to European competitions.
        cursor = await conn.execute(
            "SELECT id, name, country FROM teams ORDER BY name"
        )
        teams = await cursor.fetchall()

        # Build a quick lookup: country -> domestic competition id
        country_to_domestic_comp: dict[str, int] = {}
        for row in competitions:
            comp_id, comp_name, comp_country = row[0], row[1], row[2]
            # Domestic leagues have tier=5 and non-"Europe" country
            if comp_country != "Europe":
                country_to_domestic_comp[comp_country] = comp_id

        for row in teams:
            team_id, team_name, team_country = row[0], row[1], row[2]
            team_slug = to_slug(team_name)
            cache.team_country[team_id] = team_country

            if team_country and team_country in country_to_domestic_comp:
                comp_id = country_to_domestic_comp[team_country]
                cache.team_by_competition_slug[comp_id][team_slug] = (
                    team_id,
                    team_name,
                )

        await conn.close()
    except Exception:
        await conn.close()
        raise

    _cache = cache
    return cache


def get_slug_cache() -> SlugCache:
    """Return the current slug cache.

    Raises:
        RuntimeError: If the cache has not been built yet (call
            build_slug_cache() during app startup).

    Returns:
        The populated SlugCache instance.
    """
    if _cache is None:
        raise RuntimeError(
            "Slug cache not initialized. Call build_slug_cache() on startup."
        )
    return _cache


def resolve_path(path: str) -> PageContext | None:
    """Resolve a URL path to a PageContext.

    Parses the hierarchical URL scheme:
        - "" or "/" -> global
        - "england" -> nation
        - "england/premier-league" -> league
        - "england/premier-league/liverpool" -> team

    Args:
        path: The URL path (without leading slash), e.g.,
            "england/premier-league/liverpool".

    Returns:
        A PageContext if the path is valid, or None if it cannot be resolved
        (indicating a 404).
    """
    cache = get_slug_cache()

    # Normalize: strip leading/trailing slashes, lowercase
    path = path.strip("/").lower()

    # Global context
    if not path:
        return PageContext(level="global")

    segments = path.split("/")

    # Filter out empty segments (double slashes)
    segments = [s for s in segments if s]

    if len(segments) > 3:
        return None

    # Segment 1: country
    country_slug = segments[0]
    if country_slug not in COUNTRY_SLUGS:
        return None
    country_name = COUNTRY_SLUGS[country_slug]

    if len(segments) == 1:
        return PageContext(level="nation", country=country_name)

    # Segment 2: competition
    comp_slug = segments[1]
    country_comps = cache.competition_by_country_slug.get(country_slug, {})
    if comp_slug not in country_comps:
        return None
    comp_id, comp_name = country_comps[comp_slug]

    if len(segments) == 2:
        return PageContext(
            level="league",
            country=country_name,
            competition=comp_name,
            competition_id=comp_id,
        )

    # Segment 3: team
    team_slug = segments[2]
    comp_teams = cache.team_by_competition_slug.get(comp_id, {})
    if team_slug not in comp_teams:
        return None
    team_id, team_name = comp_teams[team_slug]

    return PageContext(
        level="team",
        country=country_name,
        competition=comp_name,
        competition_id=comp_id,
        team_id=team_id,
        team_name=team_name,
    )
