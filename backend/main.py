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
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from backend.models import (
    ErrorResponse,
    FixturePrediction,
    FixtureResponse,
    FixtureTeam,
    FixturesResponse,
    HealthResponse,
    LeagueInfo,
    LeaguesResponse,
    MatchSummary,
    PredictionAccuracyResponse,
    PredictionResponse,
    RankingEntry,
    RankingsResponse,
    RatingHistoryPoint,
    SearchResponse,
    TeamDetail,
    TeamHistoryResponse,
    TeamResultEntry,
    TeamResultsResponse,
    TeamSearchResult,
    TeamStatsCard,
)
from src.config import EloSettings
from src.db.connection import get_async_connection, get_db_path
from src.prediction import predict_match

_settings = EloSettings()


# Database connection pool managed at application lifecycle
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle (startup/shutdown)."""
    # Startup: verify database exists
    db_path = get_db_path()
    if not db_path.exists():
        raise RuntimeError(
            f"Database not found at {db_path}. Run pipeline first: uv run python -c 'from src.pipeline import run_pipeline; run_pipeline()'"
        )

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


# --- Frontend Pages ---


@app.get("/", response_class=HTMLResponse, tags=["Frontend"])
async def home(request: Request):
    """Home page - rankings view."""
    return templates.TemplateResponse(
        request, "rankings.html",
        {"today": date.today().isoformat()},
    )


@app.get("/predict", response_class=HTMLResponse, tags=["Frontend"])
async def predict_page(request: Request):
    """Match prediction page."""
    return templates.TemplateResponse(request, "predict.html")


@app.get("/team/{team_id}", response_class=HTMLResponse, tags=["Frontend"])
async def team_page(
    request: Request,
    team_id: int,
    league: str | None = Query(None, description="League context for navigation"),
):
    """Team detail page with Elo trajectory chart and recent matches."""
    # Fetch team name for page title (will be loaded again via API in Alpine.js)
    conn = await get_async_connection()
    try:
        cursor = await conn.execute(
            "SELECT name FROM teams WHERE id = ?", (team_id,)
        )
        team_row = await cursor.fetchone()
        await conn.close()

        if team_row is None:
            raise HTTPException(status_code=404, detail=f"Team with ID {team_id} not found")

        team_name = team_row[0]

        # Map league codes to display names
        league_names = {
            'epl': 'Premier League',
            'laliga': 'La Liga',
            'bundesliga': 'Bundesliga',
            'seriea': 'Serie A',
            'ligue1': 'Ligue 1',
        }
        league_name = league_names.get(league, '') if league else ''

        return templates.TemplateResponse(
            request, "team.html",
            {
                "team_id": team_id,
                "team_name": team_name,
                "league": league,
                "league_name": league_name,
            },
        )
    except HTTPException:
        await conn.close()
        raise


@app.get("/compare", response_class=HTMLResponse, tags=["Frontend"])
async def compare_page(
    request: Request,
    league: str | None = Query(None, description="League code to filter teams"),
):
    """Multi-team comparison chart page.

    Query parameters:
        league: Show top 7 teams from league (epl, laliga, bundesliga, seriea, ligue1)
        competition: Show top 7 teams from competition (cl, el, conference)
        teams: Show specific teams by ID (comma-separated, e.g., "1,2,3")

    If no parameters provided, shows global top 7 teams.
    """
    return templates.TemplateResponse(
        request, "compare.html",
        {"league": league},
    )


@app.get("/fixtures", response_class=HTMLResponse, tags=["Frontend"])
async def fixtures_page(request: Request):
    """Upcoming fixtures with Elo predictions."""
    return templates.TemplateResponse(request, "fixtures.html")


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
    description="Get current or historical Elo rankings. Optionally filter by date.",
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
    limit: int = Query(
        50,
        description="Maximum number of teams to return",
        ge=1,
        le=500,
    ),
):
    """Get team rankings sorted by Elo rating.

    Returns current rankings if no date specified, otherwise returns rankings
    as of the specified date. Optionally filter by country.
    """
    conn = await get_async_connection()

    try:
        if date is None:
            # Current rankings - latest rating per team
            if country:
                cursor = await conn.execute(
                    """SELECT t.id, t.name, t.country, rh.rating
                       FROM ratings_history rh
                       JOIN teams t ON t.id = rh.team_id
                       WHERE rh.id IN (
                           SELECT id FROM ratings_history rh2
                           WHERE rh2.team_id = rh.team_id
                           ORDER BY rh2.date DESC, rh2.id DESC
                           LIMIT 1
                       ) AND t.country = ?
                       ORDER BY rh.rating DESC
                       LIMIT ?""",
                    (country, limit),
                )
            else:
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
                       ORDER BY rh.rating DESC
                       LIMIT ?""",
                    (limit,),
                )
        else:
            # Historical rankings at specific date
            if country:
                cursor = await conn.execute(
                    """SELECT t.id, t.name, t.country, rh.rating
                       FROM ratings_history rh
                       JOIN teams t ON t.id = rh.team_id
                       WHERE rh.id IN (
                           SELECT rh2.id FROM ratings_history rh2
                           WHERE rh2.team_id = rh.team_id AND rh2.date <= ?
                           ORDER BY rh2.date DESC, rh2.id DESC
                           LIMIT 1
                       ) AND t.country = ?
                       ORDER BY rh.rating DESC
                       LIMIT ?""",
                    (date, country, limit),
                )
            else:
                cursor = await conn.execute(
                    """SELECT t.id, t.name, t.country, rh.rating
                       FROM ratings_history rh
                       JOIN teams t ON t.id = rh.team_id
                       WHERE rh.id IN (
                           SELECT rh2.id FROM ratings_history rh2
                           WHERE rh2.team_id = rh.team_id AND rh2.date <= ?
                           ORDER BY rh2.date DESC, rh2.id DESC
                           LIMIT 1
                       )
                       ORDER BY rh.rating DESC
                       LIMIT ?""",
                    (date, limit),
                )

        rows = await cursor.fetchall()
        await conn.close()

        rankings = [
            RankingEntry(
                rank=i + 1,
                team=row[1],
                team_id=row[0],
                country=row[2],
                rating=round(row[3], 1),
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
):
    """Get aggregate prediction accuracy based on Brier scores."""
    from src.live.prediction_tracker import get_prediction_accuracy

    try:
        result = await get_prediction_accuracy(competition=competition)
        return PredictionAccuracyResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error computing accuracy: {str(e)}")
