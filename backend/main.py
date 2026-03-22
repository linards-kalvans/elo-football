"""FastAPI application for Football Elo Rating System.

Provides REST API endpoints for querying team ratings, rankings, predictions,
and match history.
"""

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import date

import aiosqlite
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from backend.models import (
    ErrorResponse,
    FixturePrediction,
    FixtureResponse,
    FixtureTeam,
    FixturesResponse,
    HealthResponse,
    OutcomeGridCell,
    OutcomeGridRow,
    LeagueInfo,
    LeaguesResponse,
    MatchSummary,
    PredictionAccuracyResponse,
    PredictionGridResponse,
    PredictionHistoryResponse,
    PredictionResponse,
    RankingEntry,
    RankingsContextResponse,
    RankingsResponse,
    RatingHistoryPoint,
    ScopedAccuracyResponse,
    ScopedChartResponse,
    ScopedFixtureEntry,
    ScopedFixturesResponse,
    SearchResponse,
    SidebarCompetition,
    SidebarNation,
    SidebarResponse,
    TeamDetail,
    TeamHistoryResponse,
    TeamRatingHistory,
    TeamResultEntry,
    TeamResultsResponse,
    TeamSearchResult,
    TeamStatsCard,
)
from backend.slugs import (
    COMPETITION_LOGO_URLS,
    COUNTRY_FLAG_URLS,
    build_slug_cache,
    get_slug_cache,
    resolve_path,
    to_slug,
)
from src.config import EloSettings
from src.db.connection import get_async_connection, get_db_path
from src.db.migrate import run_migrations
from src.prediction import predict_match

# Cache for sidebar data (changes rarely)
_sidebar_cache: dict | None = None
_sidebar_cache_time: float = 0

_settings = EloSettings()


# Database connection pool managed at application lifecycle
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle (startup/shutdown)."""
    # Startup: ensure data directory and schema exist
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if not db_path.exists():
        print(f"Database not found at {db_path}. Creating empty database and applying migrations.")
    await run_migrations(db_path=db_path, verbose=True)

    # Build slug lookup cache for URL path resolution
    await build_slug_cache()

    yield

    # Shutdown: cleanup if needed
    pass


app = FastAPI(
    title="Football Elo Rating API",
    description="""
    REST API for querying European football club Elo ratings across 5 domestic leagues
    and European competitions (Champions League, Europa League, Conference League).

    Features:
    - Current and historical team rankings
    - Team rating trajectories over time
    - Match outcome predictions based on Elo ratings
    - Full-text team search

    Data coverage: 300 teams, 20,833 matches (2015-2026).
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS configuration
_cors_origins = os.environ.get("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Templates and static files
templates = Jinja2Templates(directory="backend/templates")
templates.env.filters["to_slug"] = to_slug
app.mount("/static", StaticFiles(directory="backend/static"), name="static")


# --- Error Handlers ---


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    """Return consistent error response format."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.__class__.__name__,
            "message": exc.detail,
            "detail": None,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    """Catch-all for unexpected errors."""
    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred",
            "detail": str(exc) if app.debug else None,
        },
    )


# --- Legacy URL Redirects ---
# Old multi-page routes redirect to the unified layout.


@app.get("/predict", tags=["Redirects"])
async def redirect_predict():
    """Redirect old /predict page to unified layout."""
    return RedirectResponse(url="/", status_code=302)


@app.get("/compare", tags=["Redirects"])
async def redirect_compare():
    """Redirect old /compare page to unified layout."""
    return RedirectResponse(url="/", status_code=302)


@app.get("/fixtures", tags=["Redirects"])
async def redirect_fixtures():
    """Redirect old /fixtures page to unified layout."""
    return RedirectResponse(url="/", status_code=302)


@app.get("/prediction-history", tags=["Redirects"])
async def redirect_prediction_history():
    """Redirect old /prediction-history page to unified layout."""
    return RedirectResponse(url="/", status_code=302)


@app.get("/accuracy", tags=["Redirects"])
async def redirect_accuracy():
    """Redirect old /accuracy page to unified layout."""
    return RedirectResponse(url="/", status_code=302)


@app.get("/team/{team_id}", tags=["Redirects"])
async def redirect_team(team_id: int):
    """Redirect old /team/{id} URLs to the new slug-based URL.

    Looks up the team's name and country, resolves its domestic league,
    and builds the canonical slug URL (e.g., /england/premier-league/liverpool).
    Falls back to / if resolution fails.
    """
    try:
        conn = await get_async_connection()
        cursor = await conn.execute(
            "SELECT name, country FROM teams WHERE id = ?", (team_id,)
        )
        team_row = await cursor.fetchone()
        await conn.close()

        if team_row is None:
            return RedirectResponse(url="/", status_code=302)

        team_name, team_country = team_row[0], team_row[1]

        # Build slug URL using the slug cache
        cache = get_slug_cache()
        country_slug = to_slug(team_country)
        team_slug = to_slug(team_name)

        # Find the domestic competition for this country
        country_comps = cache.competition_by_country_slug.get(country_slug, {})
        comp_slug = None
        for cs, (comp_id, _comp_name) in country_comps.items():
            comp_teams = cache.team_by_competition_slug.get(comp_id, {})
            if team_slug in comp_teams:
                comp_slug = cs
                break

        if comp_slug:
            return RedirectResponse(
                url=f"/{country_slug}/{comp_slug}/{team_slug}",
                status_code=302,
            )
        return RedirectResponse(url="/", status_code=302)
    except Exception:
        return RedirectResponse(url="/", status_code=302)


# --- API Endpoints ---


@app.get(
    "/api/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Check API and database status",
    tags=["System"],
)
async def health_check():
    """Health check endpoint - verifies API and database connectivity."""
    try:
        conn = await get_async_connection()

        # Get database stats
        cursor = await conn.execute("SELECT COUNT(*) as cnt FROM teams")
        row = await cursor.fetchone()
        total_teams = row[0] if row else None

        cursor = await conn.execute("SELECT COUNT(*) as cnt FROM matches")
        row = await cursor.fetchone()
        total_matches = row[0] if row else None

        cursor = await conn.execute("SELECT MAX(date) as max_date FROM matches")
        row = await cursor.fetchone()
        latest_match_date = row[0] if row else None

        await conn.close()

        return HealthResponse(
            status="ok",
            version="1.0.0",
            database_connected=True,
            total_teams=total_teams,
            total_matches=total_matches,
            latest_match_date=latest_match_date,
        )
    except Exception as e:
        return HealthResponse(
            status="degraded",
            version="1.0.0",
            database_connected=False,
            total_teams=None,
            total_matches=None,
            latest_match_date=None,
        )


@app.get(
    "/api/rankings",
    response_model=RankingsResponse,
    summary="Get team rankings",
    description="Get current or historical Elo rankings. Filter by country, league, or date. Includes 7-day Elo change.",
    tags=["Rankings"],
)
async def get_rankings(
    date: str | None = Query(
        None,
        description="Date for historical rankings (YYYY-MM-DD). Omit for current rankings.",
        examples=["2024-12-31"],
    ),
    country: str | None = Query(
        None,
        description="Filter by country (e.g., England, Spain, Germany, Italy, France)",
        examples=["England"],
    ),
    league: str | None = Query(
        None,
        description="Filter by league/competition name (e.g., 'Premier League')",
        examples=["Premier League"],
    ),
    limit: int = Query(
        50,
        description="Maximum number of teams to return",
        ge=1,
        le=500,
    ),
):
    """Get team rankings sorted by Elo rating.

    Returns current rankings if no date specified, otherwise returns rankings
    as of the specified date. Optionally filter by country or league. Each
    entry includes 7-day Elo change for current rankings.
    """
    from datetime import datetime, timedelta

    conn = await get_async_connection()

    try:
        # Build the query based on filters
        if league:
            # League filter: find teams that play in this competition
            # A team plays in a competition if they have matches in it
            base_query = """
                SELECT t.id, t.name, t.country, rh.rating
                FROM ratings_history rh
                JOIN teams t ON t.id = rh.team_id
                WHERE rh.id IN (
                    SELECT id FROM ratings_history rh2
                    WHERE rh2.team_id = rh.team_id
                    {date_filter}
                    ORDER BY rh2.date DESC, rh2.id DESC
                    LIMIT 1
                )
                AND t.id IN (
                    SELECT DISTINCT home_team_id FROM matches m
                    JOIN competitions c ON c.id = m.competition_id
                    WHERE c.name = ?
                      AND m.date >= date('now', '-12 months')
                    UNION
                    SELECT DISTINCT away_team_id FROM matches m
                    JOIN competitions c ON c.id = m.competition_id
                    WHERE c.name = ?
                      AND m.date >= date('now', '-12 months')
                )
                ORDER BY rh.rating DESC
                LIMIT ?
            """
            if date:
                query = base_query.format(
                    date_filter="AND rh2.date <= ?"
                )
                params = (date, league, league, limit)
            else:
                query = base_query.format(date_filter="")
                params = (league, league, limit)
        elif date is not None:
            if country:
                query = """SELECT t.id, t.name, t.country, rh.rating
                           FROM ratings_history rh
                           JOIN teams t ON t.id = rh.team_id
                           WHERE rh.id IN (
                               SELECT rh2.id FROM ratings_history rh2
                               WHERE rh2.team_id = rh.team_id AND rh2.date <= ?
                               ORDER BY rh2.date DESC, rh2.id DESC
                               LIMIT 1
                           ) AND t.country = ?
                           ORDER BY rh.rating DESC
                           LIMIT ?"""
                params = (date, country, limit)
            else:
                query = """SELECT t.id, t.name, t.country, rh.rating
                           FROM ratings_history rh
                           JOIN teams t ON t.id = rh.team_id
                           WHERE rh.id IN (
                               SELECT rh2.id FROM ratings_history rh2
                               WHERE rh2.team_id = rh.team_id AND rh2.date <= ?
                               ORDER BY rh2.date DESC, rh2.id DESC
                               LIMIT 1
                           )
                           ORDER BY rh.rating DESC
                           LIMIT ?"""
                params = (date, limit)
        else:
            if country:
                query = """SELECT t.id, t.name, t.country, rh.rating
                           FROM ratings_history rh
                           JOIN teams t ON t.id = rh.team_id
                           WHERE rh.id IN (
                               SELECT id FROM ratings_history rh2
                               WHERE rh2.team_id = rh.team_id
                               ORDER BY rh2.date DESC, rh2.id DESC
                               LIMIT 1
                           ) AND t.country = ?
                           ORDER BY rh.rating DESC
                           LIMIT ?"""
                params = (country, limit)
            else:
                query = """SELECT t.id, t.name, t.country, rh.rating
                           FROM ratings_history rh
                           JOIN teams t ON t.id = rh.team_id
                           WHERE rh.id IN (
                               SELECT id FROM ratings_history rh2
                               WHERE rh2.team_id = rh.team_id
                               ORDER BY rh2.date DESC, rh2.id DESC
                               LIMIT 1
                           )
                           ORDER BY rh.rating DESC
                           LIMIT ?"""
                params = (limit,)

        cursor = await conn.execute(query, params)
        rows = await cursor.fetchall()

        # Compute 7d change for current rankings (not historical)
        team_ids = [row[0] for row in rows]
        change_7d_map: dict[int, float | None] = {}

        if date is None and team_ids:
            seven_days_ago = (
                datetime.now() - timedelta(days=7)
            ).strftime("%Y-%m-%d")
            placeholders = ",".join("?" * len(team_ids))
            cursor = await conn.execute(
                f"""SELECT rh.team_id, rh.rating
                    FROM ratings_history rh
                    WHERE rh.team_id IN ({placeholders})
                      AND rh.id IN (
                          SELECT rh2.id FROM ratings_history rh2
                          WHERE rh2.team_id = rh.team_id
                            AND rh2.date <= ?
                          ORDER BY rh2.date DESC, rh2.id DESC
                          LIMIT 1
                      )""",
                (*team_ids, seven_days_ago),
            )
            old_rows = await cursor.fetchall()
            old_ratings = {r[0]: r[1] for r in old_rows}

            for row in rows:
                tid, current_rating = row[0], row[3]
                old_rating = old_ratings.get(tid)
                if old_rating is not None:
                    change_7d_map[tid] = round(current_rating - old_rating, 1)
                else:
                    change_7d_map[tid] = None

        await conn.close()

        rankings = [
            RankingEntry(
                rank=i + 1,
                team=row[1],
                team_id=row[0],
                country=row[2],
                rating=round(row[3], 1),
                change_7d=change_7d_map.get(row[0]),
            )
            for i, row in enumerate(rows)
        ]

        return RankingsResponse(date=date, count=len(rankings), rankings=rankings)

    except Exception as e:
        await conn.close()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get(
    "/api/teams/{team_id}",
    response_model=TeamDetail,
    summary="Get team details",
    description="Get detailed information about a specific team including current rating and recent matches.",
    tags=["Teams"],
    responses={404: {"model": ErrorResponse, "description": "Team not found"}},
)
async def get_team_detail(team_id: int):
    """Get detailed team information including current rating and recent matches."""
    conn = await get_async_connection()

    try:
        # Get team info
        cursor = await conn.execute(
            "SELECT id, name, country, aliases FROM teams WHERE id = ?",
            (team_id,),
        )
        team_row = await cursor.fetchone()

        if team_row is None:
            await conn.close()
            raise HTTPException(status_code=404, detail=f"Team with ID {team_id} not found")

        team_id_val, team_name, country, aliases_json = team_row
        import json
        aliases = json.loads(aliases_json) if aliases_json else []

        # Get current rating
        cursor = await conn.execute(
            """SELECT rating FROM ratings_history
               WHERE team_id = ?
               ORDER BY date DESC, id DESC
               LIMIT 1""",
            (team_id_val,),
        )
        rating_row = await cursor.fetchone()
        current_rating = round(rating_row[0], 1) if rating_row else None

        # Get current rank
        rank = None
        if current_rating is not None:
            cursor = await conn.execute(
                """SELECT COUNT(*) + 1 as rank
                   FROM (
                       SELECT MAX(rh.rating) as max_rating
                       FROM ratings_history rh
                       WHERE rh.id IN (
                           SELECT id FROM ratings_history rh2
                           WHERE rh2.team_id = rh.team_id
                           ORDER BY rh2.date DESC, rh2.id DESC
                           LIMIT 1
                       )
                       GROUP BY rh.team_id
                   )
                   WHERE max_rating > ?""",
                (current_rating,),
            )
            rank_row = await cursor.fetchone()
            rank = rank_row[0] if rank_row else None

        # Get recent matches
        cursor = await conn.execute(
            """SELECT m.date, th.name as home_team, ta.name as away_team,
                      m.home_goals, m.away_goals, m.result, c.name as competition
               FROM matches m
               JOIN teams th ON th.id = m.home_team_id
               JOIN teams ta ON ta.id = m.away_team_id
               JOIN competitions c ON c.id = m.competition_id
               WHERE m.home_team_id = ? OR m.away_team_id = ?
               ORDER BY m.date DESC, m.id DESC
               LIMIT 10""",
            (team_id_val, team_id_val),
        )
        match_rows = await cursor.fetchall()

        recent_matches = [
            MatchSummary(
                date=row[0],
                home_team=row[1],
                away_team=row[2],
                home_goals=row[3],
                away_goals=row[4],
                result=row[5],
                competition=row[6],
            )
            for row in match_rows
        ]

        await conn.close()

        return TeamDetail(
            id=team_id_val,
            name=team_name,
            country=country,
            aliases=aliases,
            current_rating=current_rating,
            rank=rank,
            recent_matches=recent_matches,
        )

    except HTTPException:
        await conn.close()
        raise
    except Exception as e:
        await conn.close()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get(
    "/api/teams/{team_id}/history",
    response_model=TeamHistoryResponse,
    summary="Get team rating history",
    description="Get full Elo rating trajectory for a team over time (for charting).",
    tags=["Teams"],
    responses={404: {"model": ErrorResponse, "description": "Team not found"}},
)
async def get_team_history(
    team_id: int,
    limit: int = Query(500, description="Maximum number of history points", ge=1, le=2000),
):
    """Get full Elo rating history for a team."""
    conn = await get_async_connection()

    try:
        # Verify team exists
        cursor = await conn.execute(
            "SELECT name FROM teams WHERE id = ?", (team_id,)
        )
        team_row = await cursor.fetchone()

        if team_row is None:
            await conn.close()
            raise HTTPException(status_code=404, detail=f"Team with ID {team_id} not found")

        team_name = team_row[0]

        # Get rating history (filtered by display_from_date)
        cursor = await conn.execute(
            """SELECT date, rating, rating_delta
               FROM ratings_history
               WHERE team_id = ? AND date >= ?
               ORDER BY date ASC, id ASC
               LIMIT ?""",
            (team_id, _settings.display_from_date, limit),
        )
        rows = await cursor.fetchall()
        await conn.close()

        history = [
            RatingHistoryPoint(
                date=row[0],
                rating=round(row[1], 1),
                rating_delta=round(row[2], 1),
            )
            for row in rows
        ]

        return TeamHistoryResponse(team=team_name, history=history)

    except HTTPException:
        await conn.close()
        raise
    except Exception as e:
        await conn.close()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get(
    "/api/teams/{team_id}/results",
    response_model=TeamResultsResponse,
    summary="Get team results with Elo data",
    description="Get recent match results enriched with pre/post-match Elo ratings and stats.",
    tags=["Teams"],
    responses={404: {"model": ErrorResponse, "description": "Team not found"}},
)
async def get_team_results(
    team_id: int,
    limit: int = Query(10, description="Number of recent matches", ge=1, le=50),
):
    """Get enriched match results and stats card for a team."""
    import json
    from datetime import datetime, timedelta

    conn = await get_async_connection()

    try:
        # Verify team exists
        cursor = await conn.execute(
            "SELECT id, name, country FROM teams WHERE id = ?", (team_id,)
        )
        team_row = await cursor.fetchone()
        if team_row is None:
            await conn.close()
            raise HTTPException(status_code=404, detail=f"Team with ID {team_id} not found")

        team_name = team_row[1]

        # Get current rating and rank
        cursor = await conn.execute(
            """SELECT rating FROM ratings_history
               WHERE team_id = ? ORDER BY date DESC, id DESC LIMIT 1""",
            (team_id,),
        )
        rating_row = await cursor.fetchone()
        current_rating = round(rating_row[0], 1) if rating_row else 1400.0

        cursor = await conn.execute(
            """SELECT COUNT(*) + 1 FROM (
                   SELECT MAX(rh.rating) as max_rating
                   FROM ratings_history rh
                   WHERE rh.id IN (
                       SELECT id FROM ratings_history rh2
                       WHERE rh2.team_id = rh.team_id
                       ORDER BY rh2.date DESC, rh2.id DESC LIMIT 1
                   ) GROUP BY rh.team_id
               ) WHERE max_rating > ?""",
            (current_rating,),
        )
        rank_row = await cursor.fetchone()
        rank = rank_row[0] if rank_row else 1

        # Get recent matches with Elo data
        cursor = await conn.execute(
            """SELECT m.date, th.name, ta.name,
                      m.home_goals, m.away_goals, m.result,
                      c.name as comp,
                      m.home_team_id, m.away_team_id
               FROM matches m
               JOIN teams th ON th.id = m.home_team_id
               JOIN teams ta ON ta.id = m.away_team_id
               JOIN competitions c ON c.id = m.competition_id
               WHERE m.home_team_id = ? OR m.away_team_id = ?
               ORDER BY m.date DESC, m.id DESC
               LIMIT ?""",
            (team_id, team_id, limit),
        )
        match_rows = await cursor.fetchall()

        # Get rating history for this team (for Elo before/after calc)
        cursor = await conn.execute(
            """SELECT date, rating, rating_delta
               FROM ratings_history WHERE team_id = ?
               ORDER BY date DESC, id DESC LIMIT ?""",
            (team_id, limit + 50),
        )
        history_rows = await cursor.fetchall()

        # Build a list of (date, rating, delta) for lookup
        history_list = [(r[0], r[1], r[2]) for r in history_rows]

        # Build enriched results
        results = []
        form = []
        for match in match_rows:
            m_date, home_name, away_name = match[0], match[1], match[2]
            home_goals, away_goals, result = match[3], match[4], match[5]
            comp = match[6]
            is_home = match[7] == team_id

            # Team result
            if result == 'D':
                team_result = 'D'
            elif result == 'H':
                team_result = 'W' if is_home else 'L'
            else:
                team_result = 'L' if is_home else 'W'

            # Find matching history point
            elo_after = current_rating
            elo_change = 0.0
            for h_date, h_rating, h_delta in history_list:
                if h_date == m_date:
                    elo_after = round(h_rating, 1)
                    elo_change = round(h_delta, 1)
                    break

            elo_before = round(elo_after - elo_change, 1)

            results.append(TeamResultEntry(
                date=m_date,
                home_team=home_name,
                away_team=away_name,
                home_goals=home_goals,
                away_goals=away_goals,
                result=result,
                competition=comp,
                team_result=team_result,
                elo_before=elo_before,
                elo_after=elo_after,
                elo_change=elo_change,
            ))

            if len(form) < 5:
                form.append(team_result)

        # 30-day trend
        today = datetime.now().strftime('%Y-%m-%d')
        thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        cursor = await conn.execute(
            """SELECT rating FROM ratings_history
               WHERE team_id = ? AND date <= ? ORDER BY date DESC, id DESC LIMIT 1""",
            (team_id, thirty_days_ago),
        )
        old_rating_row = await cursor.fetchone()
        trend_30d = round(current_rating - (old_rating_row[0] if old_rating_row else current_rating), 1)

        # Peak and trough (filtered by display_from_date)
        cursor = await conn.execute(
            """SELECT date, rating FROM ratings_history
               WHERE team_id = ? AND date >= ?
               ORDER BY rating DESC LIMIT 1""",
            (team_id, _settings.display_from_date),
        )
        peak_row = await cursor.fetchone()
        peak_rating = round(peak_row[1], 1) if peak_row else current_rating
        peak_date = peak_row[0] if peak_row else today

        cursor = await conn.execute(
            """SELECT date, rating FROM ratings_history
               WHERE team_id = ? AND date >= ?
               ORDER BY rating ASC LIMIT 1""",
            (team_id, _settings.display_from_date),
        )
        trough_row = await cursor.fetchone()
        trough_rating = round(trough_row[1], 1) if trough_row else current_rating
        trough_date = trough_row[0] if trough_row else today

        await conn.close()

        stats = TeamStatsCard(
            current_rating=current_rating,
            rank=rank,
            form=form,
            trend_30d=trend_30d,
            peak_rating=peak_rating,
            peak_date=peak_date,
            trough_rating=trough_rating,
            trough_date=trough_date,
        )

        return TeamResultsResponse(team=team_name, stats=stats, results=results)

    except HTTPException:
        await conn.close()
        raise
    except Exception as e:
        await conn.close()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get(
    "/api/predict",
    response_model=PredictionResponse,
    summary="Predict match outcome",
    description="Predict win/draw/loss probabilities for a match between two teams.",
    tags=["Predictions"],
    responses={
        400: {"model": ErrorResponse, "description": "Invalid team IDs"},
        404: {"model": ErrorResponse, "description": "Team not found"},
    },
)
async def predict_match_outcome(
    home: int = Query(..., description="Home team ID", examples=[42]),
    away: int = Query(..., description="Away team ID", examples=[56]),
):
    """Predict match outcome based on current Elo ratings."""
    if home == away:
        raise HTTPException(status_code=400, detail="Home and away teams must be different")

    conn = await get_async_connection()

    try:
        # Get team names in order
        cursor = await conn.execute("SELECT name FROM teams WHERE id = ?", (home,))
        home_row = await cursor.fetchone()
        if home_row is None:
            await conn.close()
            raise HTTPException(status_code=404, detail=f"Home team with ID {home} not found")
        home_name = home_row[0]

        cursor = await conn.execute("SELECT name FROM teams WHERE id = ?", (away,))
        away_row = await cursor.fetchone()
        if away_row is None:
            await conn.close()
            raise HTTPException(status_code=404, detail=f"Away team with ID {away} not found")
        away_name = away_row[0]

        # Get latest ratings for both teams
        cursor = await conn.execute(
            """SELECT rating FROM ratings_history
               WHERE team_id = ?
               ORDER BY date DESC, id DESC
               LIMIT 1""",
            (home,),
        )
        home_rating_row = await cursor.fetchone()
        if home_rating_row is None:
            await conn.close()
            raise HTTPException(
                status_code=400,
                detail=f"Team '{home_name}' has no rating history"
            )
        home_rating = home_rating_row[0]

        cursor = await conn.execute(
            """SELECT rating FROM ratings_history
               WHERE team_id = ?
               ORDER BY date DESC, id DESC
               LIMIT 1""",
            (away,),
        )
        away_rating_row = await cursor.fetchone()
        if away_rating_row is None:
            await conn.close()
            raise HTTPException(
                status_code=400,
                detail=f"Team '{away_name}' has no rating history"
            )
        away_rating = away_rating_row[0]

        await conn.close()

        # Use prediction module
        ratings = {home_name: home_rating, away_name: away_rating}
        prediction = predict_match(home_name, away_name, ratings)

        return PredictionResponse(**prediction)

    except HTTPException:
        await conn.close()
        raise
    except Exception as e:
        await conn.close()
        raise HTTPException(status_code=500, detail=f"Prediction error: {str(e)}")


@app.get(
    "/api/leagues",
    response_model=LeaguesResponse,
    summary="List available leagues",
    description="Get list of all leagues/competitions in the database.",
    tags=["Leagues"],
)
async def get_leagues():
    """List all available leagues and competitions."""
    conn = await get_async_connection()

    try:
        cursor = await conn.execute(
            """SELECT name, country, tier
               FROM competitions
               ORDER BY tier ASC, name ASC"""
        )
        rows = await cursor.fetchall()
        await conn.close()

        leagues = [
            LeagueInfo(name=row[0], country=row[1], tier=row[2])
            for row in rows
        ]

        return LeaguesResponse(count=len(leagues), leagues=leagues)

    except Exception as e:
        await conn.close()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get(
    "/api/search",
    response_model=SearchResponse,
    summary="Search teams",
    description="Full-text search for teams by name or alias.",
    tags=["Search"],
)
async def search_teams(
    q: str = Query(..., description="Search query", min_length=1, examples=["bayern"]),
    limit: int = Query(10, description="Maximum results", ge=1, le=50),
):
    """Search teams using full-text search (FTS5)."""
    conn = await get_async_connection()

    try:
        # FTS5 prefix search
        fts_query = f"{q}*"
        cursor = await conn.execute(
            """SELECT t.id, t.name, t.country, t.aliases
               FROM teams_fts
               JOIN teams t ON t.id = teams_fts.rowid
               WHERE teams_fts MATCH ?
               ORDER BY rank
               LIMIT ?""",
            (fts_query, limit),
        )
        rows = await cursor.fetchall()
        await conn.close()

        import json
        results = [
            TeamSearchResult(
                id=row[0],
                name=row[1],
                country=row[2],
                aliases=json.loads(row[3]) if row[3] else [],
            )
            for row in rows
        ]

        return SearchResponse(query=q, count=len(results), results=results)

    except Exception as e:
        await conn.close()
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")


@app.get(
    "/api/fixtures",
    response_model=FixturesResponse,
    summary="Get upcoming fixtures",
    description="Get upcoming scheduled fixtures with Elo-based predictions.",
    tags=["Fixtures"],
)
async def get_fixtures(
    competition: str | None = Query(
        None,
        description="Filter by competition name (e.g., 'Premier League')",
        examples=["Premier League"],
    ),
):
    """Get upcoming fixtures joined with predictions."""
    conn = await get_async_connection()

    try:
        if competition:
            cursor = await conn.execute(
                """SELECT f.id, f.date,
                          f.home_team_id, th.name as home_name,
                          f.away_team_id, ta.name as away_name,
                          c.name as competition,
                          p.p_home, p.p_draw, p.p_away, p.home_elo, p.away_elo
                   FROM fixtures f
                   JOIN teams th ON th.id = f.home_team_id
                   JOIN teams ta ON ta.id = f.away_team_id
                   JOIN competitions c ON c.id = f.competition_id
                   LEFT JOIN predictions p ON p.fixture_id = f.id
                   WHERE f.status = 'scheduled'
                     AND f.date >= date('now')
                     AND c.name = ?
                   ORDER BY f.date ASC, c.name ASC""",
                (competition,),
            )
        else:
            cursor = await conn.execute(
                """SELECT f.id, f.date,
                          f.home_team_id, th.name as home_name,
                          f.away_team_id, ta.name as away_name,
                          c.name as competition,
                          p.p_home, p.p_draw, p.p_away, p.home_elo, p.away_elo
                   FROM fixtures f
                   JOIN teams th ON th.id = f.home_team_id
                   JOIN teams ta ON ta.id = f.away_team_id
                   JOIN competitions c ON c.id = f.competition_id
                   LEFT JOIN predictions p ON p.fixture_id = f.id
                   WHERE f.status = 'scheduled'
                     AND f.date >= date('now')
                   ORDER BY f.date ASC, c.name ASC"""
            )

        rows = await cursor.fetchall()
        await conn.close()

        fixtures = []
        for row in rows:
            prediction = None
            if row[7] is not None:
                prediction = FixturePrediction(
                    p_home=round(row[7], 4),
                    p_draw=round(row[8], 4),
                    p_away=round(row[9], 4),
                    home_elo=round(row[10], 1),
                    away_elo=round(row[11], 1),
                )

            fixtures.append(FixtureResponse(
                date=row[1],
                home_team=FixtureTeam(id=row[2], name=row[3]),
                away_team=FixtureTeam(id=row[4], name=row[5]),
                competition=row[6],
                prediction=prediction,
            ))

        return FixturesResponse(count=len(fixtures), fixtures=fixtures)

    except Exception as e:
        await conn.close()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# --- Sprint 12: EloKit Scoped API Endpoints ---


@app.get(
    "/api/rankings/context",
    response_model=RankingsContextResponse,
    summary="Get team-context rankings",
    description="Returns the team plus 3 teams above and 3 below in its domestic league ranking.",
    tags=["Rankings"],
    responses={404: {"model": ErrorResponse, "description": "Team not found"}},
)
async def get_rankings_context(
    team_id: int = Query(..., description="Team ID to center the ranking on"),
):
    """Get surrounding teams in a team's domestic league ranking.

    Finds the team's domestic league (most recent tier-5 competition they
    played in), then returns the team +3 above and +3 below in that
    league's current Elo ranking.
    """
    from datetime import datetime, timedelta

    conn = await get_async_connection()

    try:
        # Get team info
        cursor = await conn.execute(
            "SELECT id, name, country FROM teams WHERE id = ?", (team_id,)
        )
        team_row = await cursor.fetchone()
        if team_row is None:
            await conn.close()
            raise HTTPException(
                status_code=404, detail=f"Team with ID {team_id} not found"
            )

        team_country = team_row[2]

        # Find the team's domestic league (tier 5 competition in their country)
        cursor = await conn.execute(
            """SELECT c.name FROM competitions c
               JOIN matches m ON m.competition_id = c.id
               WHERE c.tier = 5 AND c.country = ?
                 AND (m.home_team_id = ? OR m.away_team_id = ?)
               ORDER BY m.date DESC
               LIMIT 1""",
            (team_country, team_id, team_id),
        )
        league_row = await cursor.fetchone()

        if league_row is None:
            await conn.close()
            raise HTTPException(
                status_code=404,
                detail=f"No domestic league found for team {team_id}",
            )

        league_name = league_row[0]

        # Get all teams in that league with current ratings
        cursor = await conn.execute(
            """SELECT t.id, t.name, t.country, rh.rating
               FROM ratings_history rh
               JOIN teams t ON t.id = rh.team_id
               WHERE rh.id IN (
                   SELECT id FROM ratings_history rh2
                   WHERE rh2.team_id = rh.team_id
                   ORDER BY rh2.date DESC, rh2.id DESC
                   LIMIT 1
               )
               AND t.id IN (
                   SELECT DISTINCT home_team_id FROM matches m
                   JOIN competitions c ON c.id = m.competition_id
                   WHERE c.name = ?
                     AND m.date >= date('now', '-12 months')
                   UNION
                   SELECT DISTINCT away_team_id FROM matches m
                   JOIN competitions c ON c.id = m.competition_id
                   WHERE c.name = ?
                     AND m.date >= date('now', '-12 months')
               )
               ORDER BY rh.rating DESC""",
            (league_name, league_name),
        )
        all_league_teams = await cursor.fetchall()

        # Find target team's position and extract surrounding +-3
        target_idx = None
        for i, row in enumerate(all_league_teams):
            if row[0] == team_id:
                target_idx = i
                break

        if target_idx is None:
            await conn.close()
            raise HTTPException(
                status_code=404,
                detail=f"Team {team_id} not found in league {league_name}",
            )

        start = max(0, target_idx - 3)
        end = min(len(all_league_teams), target_idx + 4)
        surrounding = all_league_teams[start:end]

        # Compute 7d change for surrounding teams
        team_ids = [row[0] for row in surrounding]
        seven_days_ago = (
            datetime.now() - timedelta(days=7)
        ).strftime("%Y-%m-%d")
        placeholders = ",".join("?" * len(team_ids))
        cursor = await conn.execute(
            f"""SELECT rh.team_id, rh.rating
                FROM ratings_history rh
                WHERE rh.team_id IN ({placeholders})
                  AND rh.id IN (
                      SELECT rh2.id FROM ratings_history rh2
                      WHERE rh2.team_id = rh.team_id
                        AND rh2.date <= ?
                      ORDER BY rh2.date DESC, rh2.id DESC
                      LIMIT 1
                  )""",
            (*team_ids, seven_days_ago),
        )
        old_rows = await cursor.fetchall()
        old_ratings = {r[0]: r[1] for r in old_rows}

        await conn.close()

        rankings = [
            RankingEntry(
                rank=start + i + 1,
                team=row[1],
                team_id=row[0],
                country=row[2],
                rating=round(row[3], 1),
                change_7d=(
                    round(row[3] - old_ratings[row[0]], 1)
                    if row[0] in old_ratings
                    else None
                ),
            )
            for i, row in enumerate(surrounding)
        ]

        return RankingsContextResponse(
            team_id=team_id,
            league=league_name,
            count=len(rankings),
            rankings=rankings,
        )

    except HTTPException:
        raise
    except Exception as e:
        await conn.close()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get(
    "/api/fixtures/scoped",
    response_model=ScopedFixturesResponse,
    summary="Get scoped fixtures",
    description="Get recent finished matches and upcoming fixtures for a given scope (country, competition, or team).",
    tags=["Fixtures"],
)
async def get_scoped_fixtures(
    country: str | None = Query(
        None, description="Filter by country", examples=["England"]
    ),
    competition: str | None = Query(
        None,
        description="Filter by competition name",
        examples=["Premier League"],
    ),
    team_id: int | None = Query(
        None, description="Filter by team ID", examples=[42]
    ),
    status: str = Query(
        "both",
        description="Filter by status: finished, scheduled, or both",
        examples=["both"],
    ),
    limit: int = Query(
        3, description="Max results per category (finished/upcoming)", ge=1, le=50
    ),
    offset_finished: int = Query(
        0, description="Offset for finished matches (skip N most recent)", ge=0
    ),
    offset_upcoming: int = Query(
        0, description="Offset for upcoming fixtures (skip N nearest)", ge=0
    ),
):
    """Get scoped fixtures: recent finished + upcoming scheduled.

    Combines data from the matches table (finished) and fixtures table
    (upcoming), scoped to the given context (country, competition, team).
    """
    conn = await get_async_connection()

    try:
        finished_entries: list[ScopedFixtureEntry] = []
        upcoming_entries: list[ScopedFixtureEntry] = []
        has_more_fin = False
        has_more_upc = False

        # --- Finished matches (from matches table) ---
        if status in ("finished", "both"):
            where_parts = [f"m.date >= '{_settings.display_from_date}'"]
            params_finished: list = []

            if team_id is not None:
                where_parts.append(
                    "(m.home_team_id = ? OR m.away_team_id = ?)"
                )
                params_finished.extend([team_id, team_id])
            if competition:
                where_parts.append("c.name = ?")
                params_finished.append(competition)
            elif country:
                where_parts.append("c.country = ?")
                params_finished.append(country)

            where_sql = " AND ".join(where_parts)
            # Fetch limit+1 to detect has_more
            params_finished.extend([limit + 1, offset_finished])

            cursor = await conn.execute(
                f"""SELECT m.date,
                           m.home_team_id, th.name AS home_name,
                           m.away_team_id, ta.name AS away_name,
                           m.home_goals, m.away_goals,
                           c.name AS competition,
                           COALESCE(pm.p_home, pf.p_home) AS p_home,
                           COALESCE(pm.p_draw, pf.p_draw) AS p_draw,
                           COALESCE(pm.p_away, pf.p_away) AS p_away,
                           COALESCE(pm.home_elo, pf.home_elo) AS home_elo,
                           COALESCE(pm.away_elo, pf.away_elo) AS away_elo,
                           rh_home.rating_delta AS home_elo_change,
                           rh_away.rating_delta AS away_elo_change,
                           rh_home.rating - rh_home.rating_delta AS home_elo_before,
                           rh_away.rating - rh_away.rating_delta AS away_elo_before
                    FROM matches m
                    JOIN teams th ON th.id = m.home_team_id
                    JOIN teams ta ON ta.id = m.away_team_id
                    JOIN competitions c ON c.id = m.competition_id
                    LEFT JOIN predictions pm ON pm.match_id = m.id
                    LEFT JOIN fixtures fx
                        ON fx.date = m.date
                        AND fx.home_team_id = m.home_team_id
                        AND fx.away_team_id = m.away_team_id
                    LEFT JOIN predictions pf ON pf.fixture_id = fx.id
                    LEFT JOIN ratings_history rh_home
                        ON rh_home.match_id = m.id
                        AND rh_home.team_id = m.home_team_id
                    LEFT JOIN ratings_history rh_away
                        ON rh_away.match_id = m.id
                        AND rh_away.team_id = m.away_team_id
                    WHERE {where_sql}
                    ORDER BY m.date DESC, m.id DESC
                    LIMIT ? OFFSET ?""",
                params_finished,
            )
            finished_rows = await cursor.fetchall()

            has_more_fin = len(finished_rows) > limit
            finished_rows = finished_rows[:limit]

            for row in finished_rows:
                # row indices: 0=date, 1=home_id, 2=home_name, 3=away_id, 4=away_name,
                #              5=home_goals, 6=away_goals, 7=competition,
                #              8=p_home, 9=p_draw, 10=p_away, 11=home_elo, 12=away_elo,
                #              13=home_elo_change, 14=away_elo_change,
                #              15=home_elo_before, 16=away_elo_before
                home_elo_before = row[15]
                away_elo_before = row[16]
                prediction = None
                if row[8] is not None:
                    pred_home_elo = row[11] if row[11] is not None else home_elo_before
                    pred_away_elo = row[12] if row[12] is not None else away_elo_before
                    prediction = FixturePrediction(
                        p_home=round(row[8], 4),
                        p_draw=round(row[9], 4),
                        p_away=round(row[10], 4),
                        home_elo=round(pred_home_elo, 1) if pred_home_elo is not None else 0.0,
                        away_elo=round(pred_away_elo, 1) if pred_away_elo is not None else 0.0,
                    )
                finished_entries.append(
                    ScopedFixtureEntry(
                        date=row[0],
                        home_team=FixtureTeam(id=row[1], name=row[2]),
                        away_team=FixtureTeam(id=row[3], name=row[4]),
                        competition=row[7],
                        status="finished",
                        home_goals=row[5],
                        away_goals=row[6],
                        prediction=prediction,
                        competition_logo_url=COMPETITION_LOGO_URLS.get(row[7]),
                        home_elo_change=round(row[13], 1) if row[13] is not None else None,
                        away_elo_change=round(row[14], 1) if row[14] is not None else None,
                        home_elo_before=round(home_elo_before, 1) if home_elo_before is not None else None,
                        away_elo_before=round(away_elo_before, 1) if away_elo_before is not None else None,
                    )
                )

            # Reverse so oldest first (chronological for display)
            finished_entries.reverse()

        # --- Upcoming fixtures (from fixtures table) ---
        if status in ("scheduled", "both"):
            where_parts_up = ["f.status = 'scheduled'", "f.date >= date('now')"]
            params_upcoming: list = []

            if team_id is not None:
                where_parts_up.append(
                    "(f.home_team_id = ? OR f.away_team_id = ?)"
                )
                params_upcoming.extend([team_id, team_id])
            if competition:
                where_parts_up.append("c.name = ?")
                params_upcoming.append(competition)
            elif country:
                where_parts_up.append("c.country = ?")
                params_upcoming.append(country)

            where_sql_up = " AND ".join(where_parts_up)
            params_upcoming.extend([limit + 1, offset_upcoming])

            cursor = await conn.execute(
                f"""SELECT f.date,
                           f.home_team_id, th.name AS home_name,
                           f.away_team_id, ta.name AS away_name,
                           c.name AS competition,
                           p.p_home, p.p_draw, p.p_away,
                           p.home_elo, p.away_elo
                    FROM fixtures f
                    JOIN teams th ON th.id = f.home_team_id
                    JOIN teams ta ON ta.id = f.away_team_id
                    JOIN competitions c ON c.id = f.competition_id
                    LEFT JOIN predictions p ON p.fixture_id = f.id
                    WHERE {where_sql_up}
                    ORDER BY f.date ASC, f.id ASC
                    LIMIT ? OFFSET ?""",
                params_upcoming,
            )
            upcoming_rows = await cursor.fetchall()

            has_more_upc = len(upcoming_rows) > limit
            upcoming_rows = upcoming_rows[:limit]

            for row in upcoming_rows:
                prediction = None
                if row[6] is not None:
                    prediction = FixturePrediction(
                        p_home=round(row[6], 4),
                        p_draw=round(row[7], 4),
                        p_away=round(row[8], 4),
                        home_elo=round(row[9], 1),
                        away_elo=round(row[10], 1),
                    )
                upcoming_entries.append(
                    ScopedFixtureEntry(
                        date=row[0],
                        home_team=FixtureTeam(id=row[1], name=row[2]),
                        away_team=FixtureTeam(id=row[3], name=row[4]),
                        competition=row[5],
                        status="scheduled",
                        home_goals=None,
                        away_goals=None,
                        prediction=prediction,
                        competition_logo_url=COMPETITION_LOGO_URLS.get(row[5]),
                    )
                )

        await conn.close()

        return ScopedFixturesResponse(
            finished=finished_entries,
            upcoming=upcoming_entries,
            total_finished=len(finished_entries),
            total_upcoming=len(upcoming_entries),
            has_more_finished=has_more_fin,
            has_more_upcoming=has_more_upc,
        )

    except Exception as e:
        await conn.close()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get(
    "/api/chart/scoped",
    response_model=ScopedChartResponse,
    summary="Get scoped chart data",
    description="Get rating history for top N teams in a scope (country, competition, or single team).",
    tags=["Charts"],
)
async def get_scoped_chart(
    country: str | None = Query(
        None, description="Filter by country", examples=["England"]
    ),
    competition: str | None = Query(
        None,
        description="Filter by competition name",
        examples=["Premier League"],
    ),
    team_id: int | None = Query(
        None, description="Single team ID", examples=[42]
    ),
    top_n: int = Query(
        5, description="Number of top teams to return", ge=1, le=20
    ),
):
    """Get rating history for charting, scoped to context.

    - If team_id is given: returns that single team's history.
    - If competition is given: returns top_n teams by current Elo in that
      league.
    - If country is given: returns top_n teams by current Elo in that country.
    - Otherwise: returns global top_n.
    """
    conn = await get_async_connection()

    try:
        if team_id is not None:
            # Single team
            cursor = await conn.execute(
                "SELECT id, name FROM teams WHERE id = ?", (team_id,)
            )
            team_row = await cursor.fetchone()
            if team_row is None:
                await conn.close()
                raise HTTPException(
                    status_code=404,
                    detail=f"Team with ID {team_id} not found",
                )
            target_teams = [(team_row[0], team_row[1])]
        elif competition:
            # Top N in competition
            cursor = await conn.execute(
                """SELECT t.id, t.name, rh.rating
                   FROM ratings_history rh
                   JOIN teams t ON t.id = rh.team_id
                   WHERE rh.id IN (
                       SELECT id FROM ratings_history rh2
                       WHERE rh2.team_id = rh.team_id
                       ORDER BY rh2.date DESC, rh2.id DESC
                       LIMIT 1
                   )
                   AND t.id IN (
                       SELECT DISTINCT home_team_id FROM matches m
                       JOIN competitions c ON c.id = m.competition_id
                       WHERE c.name = ?
                         AND m.date >= date('now', '-12 months')
                       UNION
                       SELECT DISTINCT away_team_id FROM matches m
                       JOIN competitions c ON c.id = m.competition_id
                       WHERE c.name = ?
                         AND m.date >= date('now', '-12 months')
                   )
                   ORDER BY rh.rating DESC
                   LIMIT ?""",
                (competition, competition, top_n),
            )
            target_teams = [(r[0], r[1]) for r in await cursor.fetchall()]
        elif country:
            # Top N in country
            cursor = await conn.execute(
                """SELECT t.id, t.name, rh.rating
                   FROM ratings_history rh
                   JOIN teams t ON t.id = rh.team_id
                   WHERE rh.id IN (
                       SELECT id FROM ratings_history rh2
                       WHERE rh2.team_id = rh.team_id
                       ORDER BY rh2.date DESC, rh2.id DESC
                       LIMIT 1
                   )
                   AND t.country = ?
                   ORDER BY rh.rating DESC
                   LIMIT ?""",
                (country, top_n),
            )
            target_teams = [(r[0], r[1]) for r in await cursor.fetchall()]
        else:
            # Global top N
            cursor = await conn.execute(
                """SELECT t.id, t.name, rh.rating
                   FROM ratings_history rh
                   JOIN teams t ON t.id = rh.team_id
                   WHERE rh.id IN (
                       SELECT id FROM ratings_history rh2
                       WHERE rh2.team_id = rh.team_id
                       ORDER BY rh2.date DESC, rh2.id DESC
                       LIMIT 1
                   )
                   ORDER BY rh.rating DESC
                   LIMIT ?""",
                (top_n,),
            )
            target_teams = [(r[0], r[1]) for r in await cursor.fetchall()]

        # Fetch rating history for each team
        result_teams: list[TeamRatingHistory] = []
        for tid, tname in target_teams:
            cursor = await conn.execute(
                """SELECT date, rating, rating_delta
                   FROM ratings_history
                   WHERE team_id = ? AND date >= ?
                   ORDER BY date ASC, id ASC""",
                (tid, _settings.display_from_date),
            )
            history_rows = await cursor.fetchall()
            result_teams.append(
                TeamRatingHistory(
                    team_id=tid,
                    team=tname,
                    history=[
                        RatingHistoryPoint(
                            date=r[0],
                            rating=round(r[1], 1),
                            rating_delta=round(r[2], 1),
                        )
                        for r in history_rows
                    ],
                )
            )

        await conn.close()

        return ScopedChartResponse(teams=result_teams, count=len(result_teams))

    except HTTPException:
        raise
    except Exception as e:
        await conn.close()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get(
    "/api/accuracy/scoped",
    response_model=ScopedAccuracyResponse,
    summary="Get scoped prediction accuracy",
    description="Prediction accuracy stats scoped to country, competition, or team.",
    tags=["Predictions"],
)
async def get_scoped_accuracy(
    country: str | None = Query(
        None, description="Filter by country", examples=["England"]
    ),
    competition: str | None = Query(
        None,
        description="Filter by competition name",
        examples=["Premier League"],
    ),
    team_id: int | None = Query(
        None, description="Filter by team ID", examples=[42]
    ),
):
    """Get prediction accuracy for a specific scope.

    Returns accuracy percentage (correct outcome predictions), mean Brier
    score, and trend vs previous period for the given context.
    """
    import statistics

    conn = await get_async_connection()

    try:
        # Build WHERE clauses for filtering scored predictions
        where_parts = ["p.brier_score IS NOT NULL"]
        params: list = []

        if team_id is not None:
            where_parts.append(
                """(COALESCE(m.home_team_id, f.home_team_id) = ?
                   OR COALESCE(m.away_team_id, f.away_team_id) = ?)"""
            )
            params.extend([team_id, team_id])
        if competition:
            where_parts.append("COALESCE(c1.name, c2.name) = ?")
            params.append(competition)
        elif country:
            where_parts.append("COALESCE(c1.country, c2.country) = ?")
            params.append(country)

        where_sql = " AND ".join(where_parts)

        base_from = """
            FROM predictions p
            LEFT JOIN matches m ON m.id = p.match_id
            LEFT JOIN competitions c1 ON c1.id = m.competition_id
            LEFT JOIN fixtures f ON f.id = p.fixture_id
            LEFT JOIN competitions c2 ON c2.id = f.competition_id
            LEFT JOIN matches m2 ON m2.date = f.date
                AND m2.home_team_id = f.home_team_id
                AND m2.away_team_id = f.away_team_id
        """

        cursor = await conn.execute(
            f"""SELECT p.p_home, p.p_draw, p.p_away, p.brier_score,
                       COALESCE(m.result, m2.result) AS actual_result
                {base_from}
                WHERE {where_sql}
                ORDER BY p.scored_at ASC""",
            params,
        )
        rows = await cursor.fetchall()
        await conn.close()

        if not rows:
            return ScopedAccuracyResponse(
                total_predictions=0,
                accuracy_pct=None,
                mean_brier_score=None,
                trend_pct=None,
            )

        total = len(rows)
        brier_scores = [r[3] for r in rows]
        mean_brier = round(statistics.mean(brier_scores), 4)

        # Compute accuracy: prediction correct if highest probability
        # matches actual result
        correct = 0
        for row in rows:
            p_home, p_draw, p_away = row[0], row[1], row[2]
            actual = row[4]
            predicted = max(
                [("H", p_home), ("D", p_draw), ("A", p_away)],
                key=lambda x: x[1],
            )[0]
            if predicted == actual:
                correct += 1

        accuracy_pct = round(100 * correct / total, 1)

        # Trend: compare second half vs first half accuracy
        trend_pct = None
        if total >= 20:
            mid = total // 2
            first_half_correct = 0
            second_half_correct = 0
            for i, row in enumerate(rows):
                p_home, p_draw, p_away = row[0], row[1], row[2]
                actual = row[4]
                predicted = max(
                    [("H", p_home), ("D", p_draw), ("A", p_away)],
                    key=lambda x: x[1],
                )[0]
                if predicted == actual:
                    if i < mid:
                        first_half_correct += 1
                    else:
                        second_half_correct += 1

            first_pct = 100 * first_half_correct / mid
            second_pct = 100 * second_half_correct / (total - mid)
            trend_pct = round(second_pct - first_pct, 1)

        return ScopedAccuracyResponse(
            total_predictions=total,
            accuracy_pct=accuracy_pct,
            mean_brier_score=mean_brier,
            trend_pct=trend_pct,
        )

    except Exception as e:
        await conn.close()
        raise HTTPException(
            status_code=500, detail=f"Database error: {str(e)}"
        )


@app.get(
    "/api/accuracy/grid",
    response_model=PredictionGridResponse,
    summary="Get prediction performance grid",
    description=(
        "3x3 matrix of predicted vs actual outcomes with counts and "
        "percentages. Supports the same scoping as /api/accuracy/scoped."
    ),
    tags=["Predictions"],
)
async def get_accuracy_grid(
    country: str | None = Query(
        None, description="Filter by country", examples=["England"]
    ),
    competition: str | None = Query(
        None,
        description="Filter by competition name",
        examples=["Premier League"],
    ),
    team_id: int | None = Query(
        None, description="Filter by team ID", examples=[42]
    ),
    source: str | None = Query(
        None,
        description="Filter by prediction source",
        examples=["live"],
    ),
):
    """Get a 3x3 prediction performance grid.

    For each scored prediction, determines the predicted outcome (highest
    probability among H/D/A) and cross-tabulates with the actual outcome.
    Returns counts, row percentages, and total percentages for each cell.
    """
    conn = await get_async_connection()

    try:
        # Build WHERE clauses — same pattern as /api/accuracy/scoped
        where_parts = ["p.brier_score IS NOT NULL"]
        params: list = []

        if team_id is not None:
            where_parts.append(
                """(COALESCE(m.home_team_id, f.home_team_id) = ?
                   OR COALESCE(m.away_team_id, f.away_team_id) = ?)"""
            )
            params.extend([team_id, team_id])
        if competition:
            where_parts.append("COALESCE(c1.name, c2.name) = ?")
            params.append(competition)
        elif country:
            where_parts.append("COALESCE(c1.country, c2.country) = ?")
            params.append(country)
        if source:
            where_parts.append("COALESCE(p.source, 'live') = ?")
            params.append(source)

        where_sql = " AND ".join(where_parts)

        base_from = """
            FROM predictions p
            LEFT JOIN matches m ON m.id = p.match_id
            LEFT JOIN competitions c1 ON c1.id = m.competition_id
            LEFT JOIN fixtures f ON f.id = p.fixture_id
            LEFT JOIN competitions c2 ON c2.id = f.competition_id
            LEFT JOIN matches m2 ON m2.date = f.date
                AND m2.home_team_id = f.home_team_id
                AND m2.away_team_id = f.away_team_id
        """

        cursor = await conn.execute(
            f"""SELECT p.p_home, p.p_draw, p.p_away,
                       COALESCE(m.result, m2.result) AS actual_result
                {base_from}
                WHERE {where_sql}""",
            params,
        )
        rows = await cursor.fetchall()
        await conn.close()

        # Build 3x3 count matrix: matrix[actual][predicted]
        outcomes = ["H", "D", "A"]
        matrix = {a: {p: 0 for p in outcomes} for a in outcomes}

        for row in rows:
            p_home, p_draw, p_away = row[0], row[1], row[2]
            actual = row[3]
            if actual not in outcomes:
                continue
            predicted = max(
                [("H", p_home), ("D", p_draw), ("A", p_away)],
                key=lambda x: x[1],
            )[0]
            matrix[actual][predicted] += 1

        total = sum(matrix[a][p] for a in outcomes for p in outcomes)
        correct = sum(matrix[o][o] for o in outcomes)
        accuracy_pct = round(100 * correct / total, 1) if total > 0 else 0.0

        def _make_row(actual: str) -> OutcomeGridRow:
            row_total = sum(matrix[actual][p] for p in outcomes)
            cells = {}
            for pred, key in zip(
                outcomes,
                ["predicted_home", "predicted_draw", "predicted_away"],
            ):
                count = matrix[actual][pred]
                cells[key] = OutcomeGridCell(
                    count=count,
                    pct_of_row=(
                        round(100 * count / row_total, 1)
                        if row_total > 0
                        else 0.0
                    ),
                    pct_of_total=(
                        round(100 * count / total, 1)
                        if total > 0
                        else 0.0
                    ),
                )
            return OutcomeGridRow(**cells, total=row_total)

        return PredictionGridResponse(
            actual_home=_make_row("H"),
            actual_draw=_make_row("D"),
            actual_away=_make_row("A"),
            total=total,
            correct=correct,
            accuracy_pct=accuracy_pct,
        )

    except Exception as e:
        await conn.close()
        raise HTTPException(
            status_code=500, detail=f"Database error: {str(e)}"
        )


@app.get(
    "/api/sidebar",
    response_model=SidebarResponse,
    summary="Get sidebar navigation tree",
    description="Returns nations with their competitions and European competitions for sidebar navigation. Cached.",
    tags=["Navigation"],
)
async def get_sidebar():
    """Get navigation tree for sidebar.

    Returns nations grouped with their domestic competitions, plus European
    club competitions. Response is cached in-memory since this data changes
    rarely.
    """
    import time

    global _sidebar_cache, _sidebar_cache_time

    # Cache for 1 hour
    if _sidebar_cache is not None and (time.time() - _sidebar_cache_time) < 3600:
        return _sidebar_cache

    conn = await get_async_connection()

    try:
        cursor = await conn.execute(
            """SELECT id, name, country, tier
               FROM competitions
               ORDER BY country ASC, tier ASC, name ASC"""
        )
        rows = await cursor.fetchall()
        await conn.close()

        # Separate European (no country / tier < 5) from domestic (tier 5)
        nations_map: dict[str, list[SidebarCompetition]] = {}
        european: list[SidebarCompetition] = []

        for row in rows:
            comp_id, comp_name, comp_country, comp_tier = (
                row[0], row[1], row[2], row[3],
            )

            # Determine type based on tier
            comp_type = "cup" if comp_tier < 5 else "league"

            entry = SidebarCompetition(
                id=comp_id, name=comp_name, type=comp_type,
                logo_url=COMPETITION_LOGO_URLS.get(comp_name),
            )

            if comp_tier < 5 or not comp_country:
                # European competition — exclude EL/Conference League (no live data)
                if comp_name not in ("Europa League", "Conference League"):
                    european.append(entry)
            else:
                # Domestic competition
                if comp_country not in nations_map:
                    nations_map[comp_country] = []
                nations_map[comp_country].append(entry)

        nations = [
            SidebarNation(
                country=c,
                flag_url=COUNTRY_FLAG_URLS.get(c),
                competitions=comps,
            )
            for c, comps in sorted(nations_map.items())
        ]

        response = SidebarResponse(nations=nations, european=european)
        _sidebar_cache = response
        _sidebar_cache_time = time.time()

        return response

    except Exception as e:
        await conn.close()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get(
    "/api/prediction-accuracy",
    response_model=PredictionAccuracyResponse,
    summary="Get prediction accuracy stats",
    description="Aggregate prediction accuracy statistics including Brier scores and calibration data.",
    tags=["Predictions"],
)
async def prediction_accuracy(
    competition: str | None = Query(
        None,
        description="Filter by competition name (e.g., 'Premier League')",
        examples=["Premier League"],
    ),
    source: str | None = Query(
        None,
        description="Filter by prediction source ('live', 'backfill')",
        examples=["live"],
    ),
    country: str | None = Query(
        None,
        description="Filter by country name (e.g., 'England')",
        examples=["England"],
    ),
    team_id: int | None = Query(
        None,
        description="Filter by team ID",
        examples=[42],
    ),
):
    """Get aggregate prediction accuracy based on Brier scores."""
    from src.live.prediction_tracker import get_prediction_accuracy

    try:
        result = await get_prediction_accuracy(
            competition=competition, source=source,
            country=country, team_id=team_id,
        )
        return PredictionAccuracyResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error computing accuracy: {str(e)}")


@app.get(
    "/api/prediction-history",
    response_model=PredictionHistoryResponse,
    summary="Get prediction history",
    description="Paginated list of scored predictions with match details and Brier scores.",
    tags=["Predictions"],
)
async def prediction_history(
    page: int = Query(1, description="Page number (1-indexed)", ge=1),
    per_page: int = Query(
        20, description="Items per page (max 100)", ge=1, le=100
    ),
    competition: str | None = Query(
        None,
        description="Filter by competition name (e.g., 'Premier League')",
        examples=["Premier League"],
    ),
    date_from: str | None = Query(
        None,
        description="Filter from date (YYYY-MM-DD, inclusive)",
        examples=["2026-01-01"],
    ),
    date_to: str | None = Query(
        None,
        description="Filter to date (YYYY-MM-DD, inclusive)",
        examples=["2026-03-15"],
    ),
    source: str | None = Query(
        None,
        description="Filter by prediction source ('live', 'backfill')",
        examples=["live"],
    ),
    search: str | None = Query(
        None,
        description="Search by team name (whitespace-separated tokens, all must match)",
        examples=["Liverpool"],
    ),
    country: str | None = Query(
        None,
        description="Filter by country name (e.g., 'England')",
        examples=["England"],
    ),
    team_id: int | None = Query(
        None,
        description="Filter by team ID",
        examples=[42],
    ),
):
    """Get paginated scored prediction history."""
    from src.live.prediction_tracker import get_prediction_history

    try:
        result = await get_prediction_history(
            page=page,
            per_page=per_page,
            competition=competition,
            date_from=date_from,
            date_to=date_to,
            source=source,
            country=country,
            team_id=team_id,
            search=search,
        )
        return PredictionHistoryResponse(**result)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error fetching prediction history: {str(e)}"
        )


# --- Static Pages ---


@app.get("/about", response_class=HTMLResponse, tags=["Frontend"])
async def about_page(request: Request) -> HTMLResponse:
    """Render the About page with project info and planned milestones."""
    return templates.TemplateResponse(request, "about.html", {"level": "about"})


# --- Catch-All Route (must be registered LAST) ---


@app.get("/{path:path}", response_class=HTMLResponse, tags=["Frontend"])
async def unified_page(request: Request, path: str):
    """Catch-all route for the EloKit unified layout.

    Resolves the URL path to a PageContext (global, nation, league, or team)
    and renders the unified index.html template with context metadata.

    This route does NOT catch /api/*, /docs, /redoc, /openapi.json, or
    /static/* paths because those routes are registered before this one
    and FastAPI matches routes in registration order.

    Args:
        request: The incoming HTTP request.
        path: The URL path (e.g., "england/premier-league/liverpool").

    Raises:
        HTTPException: 404 if the path cannot be resolved to a valid context.
    """
    # Resolve the URL path to a page context
    context = resolve_path(path)

    if context is None:
        raise HTTPException(status_code=404, detail=f"Page not found: /{path}")

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "level": context.level,
            "country": context.country,
            "competition": context.competition,
            "competition_id": context.competition_id,
            "competition_logo_url": COMPETITION_LOGO_URLS.get(context.competition or ""),
            "team_id": context.team_id,
            "team_name": context.team_name,
            "today": date.today().isoformat(),
        },
    )
