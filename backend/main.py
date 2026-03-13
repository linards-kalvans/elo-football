"""FastAPI application for Football Elo Rating System.

Provides REST API endpoints for querying team ratings, rankings, predictions,
and match history.
"""

import asyncio
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
    HealthResponse,
    LeagueInfo,
    LeaguesResponse,
    MatchSummary,
    PredictionResponse,
    RankingEntry,
    RankingsResponse,
    RatingHistoryPoint,
    SearchResponse,
    TeamDetail,
    TeamHistoryResponse,
    TeamSearchResult,
)
from src.db.connection import get_async_connection, get_db_path
from src.prediction import predict_match


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

# CORS configuration - allow frontend development from different origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
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
        "rankings.html",
        {"request": request, "today": date.today().isoformat()},
    )


@app.get("/predict", response_class=HTMLResponse, tags=["Frontend"])
async def predict_page(request: Request):
    """Match prediction page."""
    # Will be implemented in task #7
    return JSONResponse({"message": "Prediction page - coming soon"})


@app.get("/team/{team_id}", response_class=HTMLResponse, tags=["Frontend"])
async def team_page(request: Request, team_id: int):
    """Team detail page."""
    # Will be implemented in task #6
    return JSONResponse({"message": f"Team page for ID {team_id} - coming soon"})


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
    limit: int = Query(
        50,
        description="Maximum number of teams to return",
        ge=1,
        le=500,
    ),
):
    """Get team rankings sorted by Elo rating.

    Returns current rankings if no date specified, otherwise returns rankings
    as of the specified date.
    """
    conn = await get_async_connection()

    try:
        if date is None:
            # Current rankings - latest rating per team
            cursor = await conn.execute(
                """SELECT t.name, t.country, rh.rating
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
            cursor = await conn.execute(
                """SELECT t.name, t.country, rh.rating
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
                team=row[0],
                country=row[1],
                rating=round(row[2], 1),
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

        # Get rating history
        cursor = await conn.execute(
            """SELECT date, rating, rating_delta
               FROM ratings_history
               WHERE team_id = ?
               ORDER BY date ASC, id ASC
               LIMIT ?""",
            (team_id, limit),
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


# Root redirect to docs
@app.get("/", include_in_schema=False)
async def root():
    """Redirect root to API documentation."""
    return {"message": "Football Elo Rating API", "docs": "/docs", "redoc": "/redoc"}
