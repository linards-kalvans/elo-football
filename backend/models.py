"""Pydantic models for API requests and responses.

All response models include Field descriptions and examples for auto-generated
OpenAPI documentation.
"""

from pydantic import BaseModel, Field


class TeamSummary(BaseModel):
    """Team summary for rankings and listings."""

    id: int = Field(..., description="Unique team identifier", json_schema_extra={"examples": [42]})
    name: str = Field(..., description="Team canonical name", json_schema_extra={"examples": ["Arsenal"]})
    country: str = Field(..., description="Team country", json_schema_extra={"examples": ["England"]})
    rating: float = Field(..., description="Current Elo rating", json_schema_extra={"examples": [1550.5]})


class RankingEntry(BaseModel):
    """Single entry in the rankings table."""

    rank: int = Field(..., description="Current ranking position", json_schema_extra={"examples": [1]})
    team: str = Field(..., description="Team name", json_schema_extra={"examples": ["Bayern Munich"]})
    team_id: int = Field(..., description="Team ID for detail page links", json_schema_extra={"examples": [42]})
    country: str = Field(..., description="Team country", json_schema_extra={"examples": ["Germany"]})
    rating: float = Field(..., description="Elo rating", json_schema_extra={"examples": [1836.2]})


class RankingsResponse(BaseModel):
    """Response for /api/rankings endpoint."""

    date: str | None = Field(
        None,
        description="Date for historical rankings (YYYY-MM-DD), or null for current",
        json_schema_extra={"examples": ["2024-12-31"]},
    )
    count: int = Field(..., description="Number of teams returned", json_schema_extra={"examples": [50]})
    rankings: list[RankingEntry] = Field(
        ..., description="List of ranked teams"
    )


class RatingHistoryPoint(BaseModel):
    """Single point in a team's Elo rating history."""

    date: str = Field(..., description="Match date (YYYY-MM-DD)", json_schema_extra={"examples": ["2024-01-15"]})
    rating: float = Field(..., description="Elo rating after this match", json_schema_extra={"examples": [1520.3]})
    rating_delta: float = Field(
        ..., description="Change from previous rating", json_schema_extra={"examples": [12.5]}
    )


class MatchSummary(BaseModel):
    """Summary of a single match."""

    date: str = Field(..., description="Match date (YYYY-MM-DD)", json_schema_extra={"examples": ["2024-01-15"]})
    home_team: str = Field(..., description="Home team name", json_schema_extra={"examples": ["Arsenal"]})
    away_team: str = Field(..., description="Away team name", json_schema_extra={"examples": ["Chelsea"]})
    home_goals: int = Field(..., description="Home team goals", json_schema_extra={"examples": [2]})
    away_goals: int = Field(..., description="Away team goals", json_schema_extra={"examples": [1]})
    result: str = Field(
        ..., description="Match result (H/D/A from home perspective)", json_schema_extra={"examples": ["H"]}
    )
    competition: str = Field(..., description="Competition name", json_schema_extra={"examples": ["Premier League"]})


class TeamDetail(BaseModel):
    """Detailed team information."""

    id: int = Field(..., description="Team ID", json_schema_extra={"examples": [42]})
    name: str = Field(..., description="Team name", json_schema_extra={"examples": ["Arsenal"]})
    country: str = Field(..., description="Country", json_schema_extra={"examples": ["England"]})
    aliases: list[str] = Field(
        default_factory=list,
        description="Alternative names for the team",
        json_schema_extra={"examples": [["Arsenal FC", "The Gunners"]]},
    )
    current_rating: float | None = Field(
        None, description="Current Elo rating", json_schema_extra={"examples": [1550.5]}
    )
    rank: int | None = Field(None, description="Current global rank", json_schema_extra={"examples": [8]})
    recent_matches: list[MatchSummary] = Field(
        default_factory=list, description="Recent match results (last 10)"
    )


class TeamHistoryResponse(BaseModel):
    """Full Elo rating history for a team."""

    team: str = Field(..., description="Team name", json_schema_extra={"examples": ["Arsenal"]})
    history: list[RatingHistoryPoint] = Field(
        ..., description="Rating history points"
    )


class PredictionResponse(BaseModel):
    """Match outcome prediction."""

    home_team: str = Field(..., description="Home team name", json_schema_extra={"examples": ["Arsenal"]})
    away_team: str = Field(..., description="Away team name", json_schema_extra={"examples": ["Chelsea"]})
    home_rating: float = Field(..., description="Home team Elo rating", json_schema_extra={"examples": [1550.0]})
    away_rating: float = Field(..., description="Away team Elo rating", json_schema_extra={"examples": [1480.0]})
    rating_diff: float = Field(
        ..., description="Rating difference (home - away)", json_schema_extra={"examples": [70.0]}
    )
    p_home: float = Field(
        ..., description="Home win probability (0-1)", ge=0, le=1, json_schema_extra={"examples": [0.5234]}
    )
    p_draw: float = Field(
        ..., description="Draw probability (0-1)", ge=0, le=1, json_schema_extra={"examples": [0.2545]}
    )
    p_away: float = Field(
        ..., description="Away win probability (0-1)", ge=0, le=1, json_schema_extra={"examples": [0.2221]}
    )


class LeagueInfo(BaseModel):
    """League/competition information."""

    name: str = Field(..., description="Competition name", json_schema_extra={"examples": ["Premier League"]})
    country: str = Field(..., description="Country", json_schema_extra={"examples": ["England"]})
    tier: int = Field(..., description="Competition tier (1-5, lower is higher)", json_schema_extra={"examples": [5]})


class LeaguesResponse(BaseModel):
    """Response for /api/leagues endpoint."""

    count: int = Field(..., description="Number of leagues", json_schema_extra={"examples": [8]})
    leagues: list[LeagueInfo] = Field(..., description="List of available leagues")


class TeamSearchResult(BaseModel):
    """Team search result."""

    id: int = Field(..., description="Team ID", json_schema_extra={"examples": [42]})
    name: str = Field(..., description="Team name", json_schema_extra={"examples": ["Bayern Munich"]})
    country: str = Field(..., description="Country", json_schema_extra={"examples": ["Germany"]})
    aliases: list[str] = Field(
        default_factory=list, description="Alternative names", json_schema_extra={"examples": [["FC Bayern"]]}
    )


class SearchResponse(BaseModel):
    """Response for /api/search endpoint."""

    query: str = Field(..., description="Search query", json_schema_extra={"examples": ["bayern"]})
    count: int = Field(..., description="Number of results", json_schema_extra={"examples": [1]})
    results: list[TeamSearchResult] = Field(..., description="Search results")


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="API status", json_schema_extra={"examples": ["ok"]})
    version: str = Field(..., description="API version", json_schema_extra={"examples": ["1.0.0"]})
    database_connected: bool = Field(
        ..., description="Whether database is accessible", json_schema_extra={"examples": [True]}
    )
    total_teams: int | None = Field(
        None, description="Total teams in database", json_schema_extra={"examples": [300]}
    )
    total_matches: int | None = Field(
        None, description="Total matches in database", json_schema_extra={"examples": [20833]}
    )
    latest_match_date: str | None = Field(
        None, description="Most recent match date", json_schema_extra={"examples": ["2024-12-31"]}
    )


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str = Field(..., description="Error type", json_schema_extra={"examples": ["NotFound"]})
    message: str = Field(
        ..., description="Human-readable error message", json_schema_extra={"examples": ["Team not found"]}
    )
    detail: str | None = Field(
        None, description="Additional error details", json_schema_extra={"examples": ["No team with ID 999"]}
    )


class TeamResultEntry(BaseModel):
    """Enriched match result with Elo data."""

    date: str = Field(..., description="Match date (YYYY-MM-DD)", json_schema_extra={"examples": ["2024-01-15"]})
    home_team: str = Field(..., description="Home team name", json_schema_extra={"examples": ["Arsenal"]})
    away_team: str = Field(..., description="Away team name", json_schema_extra={"examples": ["Chelsea"]})
    home_goals: int = Field(..., description="Home team goals", json_schema_extra={"examples": [2]})
    away_goals: int = Field(..., description="Away team goals", json_schema_extra={"examples": [1]})
    result: str = Field(..., description="Match result (H/D/A)", json_schema_extra={"examples": ["H"]})
    competition: str = Field(..., description="Competition name", json_schema_extra={"examples": ["Premier League"]})
    team_result: str = Field(..., description="Result for this team (W/D/L)", json_schema_extra={"examples": ["W"]})
    elo_before: float = Field(..., description="Team Elo before match", json_schema_extra={"examples": [1540.0]})
    elo_after: float = Field(..., description="Team Elo after match", json_schema_extra={"examples": [1552.5]})
    elo_change: float = Field(..., description="Elo change from match", json_schema_extra={"examples": [12.5]})


class TeamStatsCard(BaseModel):
    """Stats summary for team profile."""

    current_rating: float = Field(..., description="Current Elo rating", json_schema_extra={"examples": [1550.5]})
    rank: int = Field(..., description="Current global rank", json_schema_extra={"examples": [8]})
    form: list[str] = Field(..., description="Last 5 results (W/D/L)", json_schema_extra={"examples": [["W", "W", "D", "L", "W"]]})
    trend_30d: float = Field(..., description="Rating change over last 30 days", json_schema_extra={"examples": [15.3]})
    peak_rating: float = Field(..., description="All-time peak Elo rating", json_schema_extra={"examples": [1620.0]})
    peak_date: str = Field(..., description="Date of peak rating", json_schema_extra={"examples": ["2023-05-20"]})
    trough_rating: float = Field(..., description="All-time lowest Elo rating", json_schema_extra={"examples": [1380.0]})
    trough_date: str = Field(..., description="Date of trough rating", json_schema_extra={"examples": ["2020-11-15"]})


class TeamResultsResponse(BaseModel):
    """Response for /api/teams/{id}/results endpoint."""

    team: str = Field(..., description="Team name", json_schema_extra={"examples": ["Arsenal"]})
    stats: TeamStatsCard = Field(..., description="Team statistics summary")
    results: list[TeamResultEntry] = Field(..., description="Recent match results with Elo data")


class FixtureTeam(BaseModel):
    """Team reference within a fixture."""

    id: int = Field(..., description="Team ID", json_schema_extra={"examples": [42]})
    name: str = Field(..., description="Team name", json_schema_extra={"examples": ["Arsenal"]})


class FixturePrediction(BaseModel):
    """Pre-match Elo prediction for a fixture."""

    p_home: float = Field(..., description="Home win probability (0-1)", ge=0, le=1, json_schema_extra={"examples": [0.52]})
    p_draw: float = Field(..., description="Draw probability (0-1)", ge=0, le=1, json_schema_extra={"examples": [0.25]})
    p_away: float = Field(..., description="Away win probability (0-1)", ge=0, le=1, json_schema_extra={"examples": [0.23]})
    home_elo: float = Field(..., description="Home team Elo rating", json_schema_extra={"examples": [1550.0]})
    away_elo: float = Field(..., description="Away team Elo rating", json_schema_extra={"examples": [1480.0]})


class FixtureResponse(BaseModel):
    """Single fixture with optional prediction."""

    date: str = Field(..., description="Match date (YYYY-MM-DD)", json_schema_extra={"examples": ["2026-03-20"]})
    home_team: FixtureTeam = Field(..., description="Home team")
    away_team: FixtureTeam = Field(..., description="Away team")
    competition: str = Field(..., description="Competition name", json_schema_extra={"examples": ["Premier League"]})
    prediction: FixturePrediction | None = Field(None, description="Elo-based prediction if available")


class FixturesResponse(BaseModel):
    """Response for /api/fixtures endpoint."""

    count: int = Field(..., description="Number of fixtures", json_schema_extra={"examples": [12]})
    fixtures: list[FixtureResponse] = Field(..., description="List of upcoming fixtures")


class CalibrationBucket(BaseModel):
    """Calibration data for a probability bucket."""

    count: int = Field(..., description="Number of predictions in this bucket", json_schema_extra={"examples": [50]})
    actual_frequency: float | None = Field(
        None, description="Actual frequency of outcomes in this bucket (0-1)", json_schema_extra={"examples": [0.45]}
    )
    expected_midpoint: float = Field(
        ..., description="Midpoint of the probability bucket", json_schema_extra={"examples": [0.45]}
    )


class CompetitionAccuracy(BaseModel):
    """Brier score breakdown for a single competition."""

    count: int = Field(..., description="Number of scored predictions", json_schema_extra={"examples": [120]})
    mean_brier_score: float = Field(
        ..., description="Mean Brier score for this competition", json_schema_extra={"examples": [0.4523]}
    )


class PredictionAccuracyResponse(BaseModel):
    """Response for /api/prediction-accuracy endpoint."""

    total_predictions: int = Field(
        ..., description="Total number of scored predictions", json_schema_extra={"examples": [500]}
    )
    mean_brier_score: float | None = Field(
        None, description="Mean Brier score across all predictions (lower is better, 0=perfect, 2=worst)",
        json_schema_extra={"examples": [0.4321]},
    )
    median_brier_score: float | None = Field(
        None, description="Median Brier score", json_schema_extra={"examples": [0.4100]}
    )
    calibration: dict[str, CalibrationBucket] = Field(
        default_factory=dict, description="Calibration data by probability bucket"
    )
    by_competition: dict[str, CompetitionAccuracy] = Field(
        default_factory=dict, description="Brier score breakdown by competition"
    )
    recent_form: float | None = Field(
        None, description="Mean Brier score over the last 100 predictions", json_schema_extra={"examples": [0.4200]}
    )
