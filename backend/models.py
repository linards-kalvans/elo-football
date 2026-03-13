"""Pydantic models for API requests and responses.

All response models include Field descriptions and examples for auto-generated
OpenAPI documentation.
"""

from pydantic import BaseModel, Field


class TeamSummary(BaseModel):
    """Team summary for rankings and listings."""

    id: int = Field(..., description="Unique team identifier", example=42)
    name: str = Field(..., description="Team canonical name", example="Arsenal")
    country: str = Field(..., description="Team country", example="England")
    rating: float = Field(..., description="Current Elo rating", example=1550.5)


class RankingEntry(BaseModel):
    """Single entry in the rankings table."""

    rank: int = Field(..., description="Current ranking position", example=1)
    team: str = Field(..., description="Team name", example="Bayern Munich")
    country: str = Field(..., description="Team country", example="Germany")
    rating: float = Field(..., description="Elo rating", example=1836.2)


class RankingsResponse(BaseModel):
    """Response for /api/rankings endpoint."""

    date: str | None = Field(
        None,
        description="Date for historical rankings (YYYY-MM-DD), or null for current",
        example="2024-12-31",
    )
    count: int = Field(..., description="Number of teams returned", example=50)
    rankings: list[RankingEntry] = Field(
        ..., description="List of ranked teams"
    )


class RatingHistoryPoint(BaseModel):
    """Single point in a team's Elo rating history."""

    date: str = Field(..., description="Match date (YYYY-MM-DD)", example="2024-01-15")
    rating: float = Field(..., description="Elo rating after this match", example=1520.3)
    rating_delta: float = Field(
        ..., description="Change from previous rating", example=12.5
    )


class MatchSummary(BaseModel):
    """Summary of a single match."""

    date: str = Field(..., description="Match date (YYYY-MM-DD)", example="2024-01-15")
    home_team: str = Field(..., description="Home team name", example="Arsenal")
    away_team: str = Field(..., description="Away team name", example="Chelsea")
    home_goals: int = Field(..., description="Home team goals", example=2)
    away_goals: int = Field(..., description="Away team goals", example=1)
    result: str = Field(
        ..., description="Match result (H/D/A from home perspective)", example="H"
    )
    competition: str = Field(..., description="Competition name", example="Premier League")


class TeamDetail(BaseModel):
    """Detailed team information."""

    id: int = Field(..., description="Team ID", example=42)
    name: str = Field(..., description="Team name", example="Arsenal")
    country: str = Field(..., description="Country", example="England")
    aliases: list[str] = Field(
        default_factory=list,
        description="Alternative names for the team",
        example=["Arsenal FC", "The Gunners"],
    )
    current_rating: float | None = Field(
        None, description="Current Elo rating", example=1550.5
    )
    rank: int | None = Field(None, description="Current global rank", example=8)
    recent_matches: list[MatchSummary] = Field(
        default_factory=list, description="Recent match results (last 10)"
    )


class TeamHistoryResponse(BaseModel):
    """Full Elo rating history for a team."""

    team: str = Field(..., description="Team name", example="Arsenal")
    history: list[RatingHistoryPoint] = Field(
        ..., description="Rating history points"
    )


class PredictionResponse(BaseModel):
    """Match outcome prediction."""

    home_team: str = Field(..., description="Home team name", example="Arsenal")
    away_team: str = Field(..., description="Away team name", example="Chelsea")
    home_rating: float = Field(..., description="Home team Elo rating", example=1550.0)
    away_rating: float = Field(..., description="Away team Elo rating", example=1480.0)
    rating_diff: float = Field(
        ..., description="Rating difference (home - away)", example=70.0
    )
    p_home: float = Field(
        ..., description="Home win probability (0-1)", example=0.5234, ge=0, le=1
    )
    p_draw: float = Field(
        ..., description="Draw probability (0-1)", example=0.2545, ge=0, le=1
    )
    p_away: float = Field(
        ..., description="Away win probability (0-1)", example=0.2221, ge=0, le=1
    )


class LeagueInfo(BaseModel):
    """League/competition information."""

    name: str = Field(..., description="Competition name", example="Premier League")
    country: str = Field(..., description="Country", example="England")
    tier: int = Field(..., description="Competition tier (1-5, lower is higher)", example=5)


class LeaguesResponse(BaseModel):
    """Response for /api/leagues endpoint."""

    count: int = Field(..., description="Number of leagues", example=8)
    leagues: list[LeagueInfo] = Field(..., description="List of available leagues")


class TeamSearchResult(BaseModel):
    """Team search result."""

    id: int = Field(..., description="Team ID", example=42)
    name: str = Field(..., description="Team name", example="Bayern Munich")
    country: str = Field(..., description="Country", example="Germany")
    aliases: list[str] = Field(
        default_factory=list, description="Alternative names", example=["FC Bayern"]
    )


class SearchResponse(BaseModel):
    """Response for /api/search endpoint."""

    query: str = Field(..., description="Search query", example="bayern")
    count: int = Field(..., description="Number of results", example=1)
    results: list[TeamSearchResult] = Field(..., description="Search results")


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="API status", example="ok")
    version: str = Field(..., description="API version", example="1.0.0")
    database_connected: bool = Field(
        ..., description="Whether database is accessible", example=True
    )
    total_teams: int | None = Field(
        None, description="Total teams in database", example=300
    )
    total_matches: int | None = Field(
        None, description="Total matches in database", example=20833
    )
    latest_match_date: str | None = Field(
        None, description="Most recent match date", example="2024-12-31"
    )


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str = Field(..., description="Error type", example="NotFound")
    message: str = Field(
        ..., description="Human-readable error message", example="Team not found"
    )
    detail: str | None = Field(
        None, description="Additional error details", example="No team with ID 999"
    )
