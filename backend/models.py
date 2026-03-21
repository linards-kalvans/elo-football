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
    change_7d: float | None = Field(
        None,
        description="Elo rating change over last 7 calendar days",
        json_schema_extra={"examples": [12.5]},
    )


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


class BrierTimeSeriesPoint(BaseModel):
    """Single point in the Brier score rolling average time series."""

    date: str = Field(..., description="Date (YYYY-MM-DD)", json_schema_extra={"examples": ["2026-03-01"]})
    rolling_brier: float = Field(
        ..., description="Rolling average Brier score (window=50)", json_schema_extra={"examples": [0.42]}
    )
    count: int = Field(..., description="Number of predictions in the rolling window", json_schema_extra={"examples": [50]})


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
    by_source: dict[str, CompetitionAccuracy] = Field(
        default_factory=dict,
        description="Brier score breakdown by prediction source (live vs backfill)",
    )
    recent_form: float | None = Field(
        None, description="Mean Brier score over the last 100 predictions", json_schema_extra={"examples": [0.4200]}
    )
    time_series: list[BrierTimeSeriesPoint] = Field(
        default_factory=list, description="Rolling Brier score time series for trend chart"
    )


class PredictionHistoryItem(BaseModel):
    """Single scored prediction in the prediction history."""

    date: str = Field(..., description="Match date (YYYY-MM-DD)", json_schema_extra={"examples": ["2026-03-15"]})
    home_team: str = Field(..., description="Home team name", json_schema_extra={"examples": ["Arsenal"]})
    away_team: str = Field(..., description="Away team name", json_schema_extra={"examples": ["Chelsea"]})
    competition: str = Field(..., description="Competition name", json_schema_extra={"examples": ["Premier League"]})
    p_home: float = Field(..., description="Predicted home win probability", json_schema_extra={"examples": [0.52]})
    p_draw: float = Field(..., description="Predicted draw probability", json_schema_extra={"examples": [0.25]})
    p_away: float = Field(..., description="Predicted away win probability", json_schema_extra={"examples": [0.23]})
    actual_result: str = Field(..., description="Actual match result (H/D/A)", json_schema_extra={"examples": ["H"]})
    home_goals: int = Field(..., description="Home team goals scored", json_schema_extra={"examples": [2]})
    away_goals: int = Field(..., description="Away team goals scored", json_schema_extra={"examples": [1]})
    brier_score: float = Field(..., description="Brier score for this prediction", json_schema_extra={"examples": [0.35]})
    home_elo: float = Field(..., description="Home team Elo at prediction time", json_schema_extra={"examples": [1836]})
    away_elo: float = Field(..., description="Away team Elo at prediction time", json_schema_extra={"examples": [1650]})
    source: str = Field("live", description="Prediction source ('live' or 'backfill')", json_schema_extra={"examples": ["live"]})


class PredictionHistoryResponse(BaseModel):
    """Paginated response for /api/prediction-history endpoint."""

    items: list[PredictionHistoryItem] = Field(..., description="List of scored predictions")
    total: int = Field(..., description="Total number of matching predictions", json_schema_extra={"examples": [150]})
    page: int = Field(..., description="Current page number", json_schema_extra={"examples": [1]})
    per_page: int = Field(..., description="Items per page", json_schema_extra={"examples": [20]})
    pages: int = Field(..., description="Total number of pages", json_schema_extra={"examples": [8]})


# --- Sprint 12: EloKit Scoped API Models ---


class RankingsContextResponse(BaseModel):
    """Response for /api/rankings/context endpoint.

    Returns a team and its surrounding teams in its domestic league ranking.
    """

    team_id: int = Field(
        ..., description="Queried team ID", json_schema_extra={"examples": [42]}
    )
    league: str = Field(
        ..., description="Domestic league name",
        json_schema_extra={"examples": ["Premier League"]},
    )
    count: int = Field(
        ..., description="Number of teams returned",
        json_schema_extra={"examples": [7]},
    )
    rankings: list[RankingEntry] = Field(
        ..., description="Surrounding teams in league ranking"
    )


class ScopedFixtureEntry(BaseModel):
    """Single fixture/match entry for scoped fixtures endpoint."""

    date: str = Field(
        ..., description="Match date (YYYY-MM-DD)",
        json_schema_extra={"examples": ["2026-03-20"]},
    )
    home_team: FixtureTeam = Field(..., description="Home team")
    away_team: FixtureTeam = Field(..., description="Away team")
    competition: str = Field(
        ..., description="Competition name",
        json_schema_extra={"examples": ["Premier League"]},
    )
    status: str = Field(
        ..., description="Match status (finished/scheduled)",
        json_schema_extra={"examples": ["finished"]},
    )
    home_goals: int | None = Field(
        None, description="Home team goals (null if upcoming)",
        json_schema_extra={"examples": [2]},
    )
    away_goals: int | None = Field(
        None, description="Away team goals (null if upcoming)",
        json_schema_extra={"examples": [1]},
    )
    prediction: FixturePrediction | None = Field(
        None, description="Elo-based prediction if available"
    )
    competition_logo_url: str | None = Field(
        None, description="URL for competition logo SVG",
        json_schema_extra={"examples": ["/static/logos/competitions/premier-league.svg"]},
    )
    home_elo_change: float | None = Field(
        None, description="Home team Elo rating change from this match",
        json_schema_extra={"examples": [12.3]},
    )
    away_elo_change: float | None = Field(
        None, description="Away team Elo rating change from this match",
        json_schema_extra={"examples": [-8.5]},
    )
    home_elo_before: float | None = Field(
        None, description="Home team Elo rating before the match",
        json_schema_extra={"examples": [1550.0]},
    )
    away_elo_before: float | None = Field(
        None, description="Away team Elo rating before the match",
        json_schema_extra={"examples": [1480.0]},
    )


class ScopedFixturesResponse(BaseModel):
    """Response for /api/fixtures/scoped endpoint."""

    finished: list[ScopedFixtureEntry] = Field(
        ..., description="Recent finished matches"
    )
    upcoming: list[ScopedFixtureEntry] = Field(
        ..., description="Upcoming scheduled fixtures"
    )
    total_finished: int = Field(
        ..., description="Count of finished matches returned",
        json_schema_extra={"examples": [3]},
    )
    total_upcoming: int = Field(
        ..., description="Count of upcoming fixtures returned",
        json_schema_extra={"examples": [3]},
    )
    has_more_finished: bool = Field(
        False, description="Whether more older finished matches exist"
    )
    has_more_upcoming: bool = Field(
        False, description="Whether more upcoming fixtures exist"
    )


class TeamRatingHistory(BaseModel):
    """Rating history for a single team (used in scoped chart)."""

    team_id: int = Field(
        ..., description="Team ID", json_schema_extra={"examples": [42]}
    )
    team: str = Field(
        ..., description="Team name", json_schema_extra={"examples": ["Arsenal"]}
    )
    history: list[RatingHistoryPoint] = Field(
        ..., description="Rating history points"
    )


class ScopedChartResponse(BaseModel):
    """Response for /api/chart/scoped endpoint."""

    teams: list[TeamRatingHistory] = Field(
        ..., description="Rating histories for teams in scope"
    )
    count: int = Field(
        ..., description="Number of teams returned",
        json_schema_extra={"examples": [5]},
    )


class ScopedAccuracyResponse(BaseModel):
    """Response for /api/accuracy/scoped endpoint."""

    total_predictions: int = Field(
        ..., description="Number of scored predictions in scope",
        json_schema_extra={"examples": [120]},
    )
    accuracy_pct: float | None = Field(
        None,
        description="Percentage of correct outcome predictions (0-100)",
        json_schema_extra={"examples": [52.3]},
    )
    mean_brier_score: float | None = Field(
        None,
        description="Mean Brier score (lower is better)",
        json_schema_extra={"examples": [0.4321]},
    )
    trend_pct: float | None = Field(
        None,
        description="Accuracy change vs previous period (percentage points)",
        json_schema_extra={"examples": [1.5]},
    )


class OutcomeGridCell(BaseModel):
    """Single cell in the 3x3 prediction performance grid."""

    count: int = Field(
        ..., description="Number of matches in this cell",
        json_schema_extra={"examples": [5200]},
    )
    pct_of_row: float = Field(
        ..., description="Percentage of the actual outcome row (0-100)",
        json_schema_extra={"examples": [65.0]},
    )
    pct_of_total: float = Field(
        ..., description="Percentage of all predictions (0-100)",
        json_schema_extra={"examples": [25.7]},
    )


class OutcomeGridRow(BaseModel):
    """Row in the prediction performance grid for one actual outcome."""

    predicted_home: OutcomeGridCell = Field(
        ..., description="Cell where predicted outcome is Home"
    )
    predicted_draw: OutcomeGridCell = Field(
        ..., description="Cell where predicted outcome is Draw"
    )
    predicted_away: OutcomeGridCell = Field(
        ..., description="Cell where predicted outcome is Away"
    )
    total: int = Field(
        ..., description="Row total (all matches with this actual outcome)",
        json_schema_extra={"examples": [8000]},
    )


class PredictionGridResponse(BaseModel):
    """Response for /api/accuracy/grid — 3x3 predicted vs actual outcome grid."""

    actual_home: OutcomeGridRow = Field(
        ..., description="Row for actual Home wins"
    )
    actual_draw: OutcomeGridRow = Field(
        ..., description="Row for actual Draws"
    )
    actual_away: OutcomeGridRow = Field(
        ..., description="Row for actual Away wins"
    )
    total: int = Field(
        ..., description="Grand total of all scored predictions",
        json_schema_extra={"examples": [20263]},
    )
    correct: int = Field(
        ..., description="Number of correct predictions (diagonal sum)",
        json_schema_extra={"examples": [11563]},
    )
    accuracy_pct: float = Field(
        ..., description="Overall accuracy percentage (0-100)",
        json_schema_extra={"examples": [57.1]},
    )


class SidebarCompetition(BaseModel):
    """Single competition entry in sidebar navigation."""

    id: int = Field(..., description="Competition ID", json_schema_extra={"examples": [1]})
    name: str = Field(
        ..., description="Competition name",
        json_schema_extra={"examples": ["Premier League"]},
    )
    type: str = Field(
        ..., description="Competition type (league or cup)",
        json_schema_extra={"examples": ["league"]},
    )
    logo_url: str | None = Field(
        None, description="URL for competition logo SVG",
        json_schema_extra={"examples": ["/static/logos/competitions/premier-league.svg"]},
    )


class SidebarNation(BaseModel):
    """Nation entry with its competitions for sidebar navigation."""

    country: str = Field(
        ..., description="Country name", json_schema_extra={"examples": ["England"]}
    )
    flag_url: str | None = Field(
        None, description="URL for country flag SVG",
        json_schema_extra={"examples": ["/static/flags/england.svg"]},
    )
    competitions: list[SidebarCompetition] = Field(
        ..., description="Competitions in this country"
    )


class SidebarResponse(BaseModel):
    """Response for /api/sidebar endpoint."""

    nations: list[SidebarNation] = Field(
        ..., description="Nations with their domestic competitions"
    )
    european: list[SidebarCompetition] = Field(
        ..., description="European club competitions (CL, EL, Conference)"
    )
