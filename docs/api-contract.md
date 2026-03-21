# Football Elo Rating API Contract

**Version:** 2.0.0
**Base URL:** `http://localhost:8000` (development) | `https://api.elo-football.com` (production)
**Content-Type:** `application/json`

---

## Table of Contents

- [Overview](#overview)
- [Authentication](#authentication)
- [Error Handling](#error-handling)
- [Rate Limiting](#rate-limiting)
- [CORS Policy](#cors-policy)
- [Endpoints](#endpoints)
  - [Health Check](#get-apihealth)
  - [Rankings](#get-apirankings)
  - [Rankings Context](#get-apirankingscontext)
  - [Team Detail](#get-apiteamsteam_id)
  - [Team History](#get-apiteamsteam_idhistory)
  - [Team Results](#get-apiteamsteam_idresults)
  - [Match Prediction](#get-apipredict)
  - [Leagues](#get-apileagues)
  - [Team Search](#get-apisearch)
  - [Fixtures](#get-apifixtures)
  - [Scoped Fixtures](#get-apifixturesscoped)
  - [Scoped Chart Data](#get-apichartscoped)
  - [Sidebar Navigation](#get-apisidebar)
  - [Prediction Accuracy](#get-apiprediction-accuracy)
  - [Prediction History](#get-apiprediction-history)
  - [Scoped Accuracy](#get-apiaccuracyscoped)
  - [Accuracy Grid](#get-apiaccuracygrid)
- [Pagination Conventions](#pagination-conventions)
- [Filtering & Sorting](#filtering--sorting)
- [OpenAPI Specification](#openapi-specification)
- [Changelog](#changelog)

---

## Overview

The Football Elo Rating API provides access to Elo ratings for European football clubs across 5 domestic leagues and European competitions (Champions League, Europa League, Conference League). It powers the EloKit frontend -- a unified single-page layout with sidebar navigation, Elo charts, rankings, fixtures with predictions, and prediction accuracy analysis.

**Data coverage:**
- **Teams:** 325
- **Matches:** 31,789 (2010-2026, with 2010-2016 as warm-up period for calibration)
- **Leagues:** Premier League, La Liga, Bundesliga, Serie A, Ligue 1
- **European Competitions:** Champions League, Europa League, Conference League
- **Predictions:** 20,263+ scored predictions with Brier score validation

**Key features:**
- Current and historical team rankings with 7-day change tracking
- Team rating trajectories over time (for charting)
- Match outcome predictions based on Elo ratings
- Full-text team search (SQLite FTS5)
- Scoped fixtures, charts, and accuracy -- filtered by country, competition, or team
- Prediction tracking with Brier scores, calibration data, and performance grid
- Sidebar navigation tree with nation flags and competition logos

---

## Authentication

**Current version:** No authentication required.

**Future versions:** API key authentication may be added for production deployments.

---

## Error Handling

All errors follow a consistent JSON structure:

```json
{
  "error": "HTTPException",
  "message": "Human-readable error message",
  "detail": null
}
```

### HTTP Status Codes

| Code | Meaning | Example |
|------|---------|---------|
| `200` | Success | Request completed successfully |
| `400` | Bad Request | Invalid query parameters or malformed request |
| `404` | Not Found | Resource (team, league) does not exist |
| `500` | Internal Server Error | Database error or unexpected failure |

### Example Error Responses

**404 Not Found:**
```json
{
  "error": "HTTPException",
  "message": "Team with ID 999 not found",
  "detail": null
}
```

**400 Bad Request:**
```json
{
  "error": "HTTPException",
  "message": "Home and away teams must be different",
  "detail": null
}
```

---

## Rate Limiting

**Current version:** No rate limiting.

**Future versions:** May implement rate limiting (e.g., 100 requests/minute per IP).

---

## CORS Policy

**Development:** All origins (`*`) allowed.

**Production:** CORS should be restricted to specific domains. Configurable via `CORS_ORIGINS` environment variable (comma-separated list).

```
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, OPTIONS
Access-Control-Allow-Headers: *
```

---

## Endpoints

---

### `GET /api/health`

Health check endpoint -- verifies API and database connectivity.

**Tags:** System

#### Request

No parameters required.

#### Response

**Status:** `200 OK`

```json
{
  "status": "ok",
  "version": "1.0.0",
  "database_connected": true,
  "total_teams": 325,
  "total_matches": 31789,
  "latest_match_date": "2026-03-15"
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `status` | `string` | API status: `"ok"` or `"degraded"` |
| `version` | `string` | API version |
| `database_connected` | `boolean` | Whether database is accessible |
| `total_teams` | `integer | null` | Total teams in database |
| `total_matches` | `integer | null` | Total matches in database |
| `latest_match_date` | `string | null` | Most recent match date (YYYY-MM-DD) |

#### Example

```bash
curl http://localhost:8000/api/health
```

---

### `GET /api/rankings`

Get current or historical Elo rankings. Supports filtering by country, league, and date. Includes 7-day Elo change for current rankings.

**Tags:** Rankings

#### Request

##### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `date` | `string` | No | `null` | Date for historical rankings (YYYY-MM-DD). Omit for current rankings. |
| `country` | `string` | No | `null` | Filter by country (e.g., `England`, `Spain`, `Germany`, `Italy`, `France`) |
| `league` | `string` | No | `null` | Filter by league/competition name (e.g., `Premier League`). Teams active in this competition within the last 12 months. |
| `limit` | `integer` | No | `50` | Maximum number of teams to return (1-500) |

#### Response

**Status:** `200 OK`

```json
{
  "date": null,
  "count": 3,
  "rankings": [
    {"rank": 1, "team": "Bayern Munich", "team_id": 23, "country": "Germany", "rating": 1835.9, "change_7d": 5.2},
    {"rank": 2, "team": "Arsenal", "team_id": 17, "country": "England", "rating": 1835.7, "change_7d": -3.1},
    {"rank": 3, "team": "Barcelona", "team_id": 45, "country": "Spain", "rating": 1757.1, "change_7d": null}
  ]
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `date` | `string | null` | Date of rankings (or null for current) |
| `count` | `integer` | Number of teams returned |
| `rankings` | `array` | List of ranking entries |
| `rankings[].rank` | `integer` | Ranking position |
| `rankings[].team` | `string` | Team name |
| `rankings[].team_id` | `integer` | Team ID |
| `rankings[].country` | `string` | Team country |
| `rankings[].rating` | `number` | Elo rating |
| `rankings[].change_7d` | `number | null` | Rating change over last 7 days (null for historical or no prior data) |

#### Examples

```bash
# Current rankings (top 50)
curl http://localhost:8000/api/rankings

# Current top 10
curl "http://localhost:8000/api/rankings?limit=10"

# English teams only
curl "http://localhost:8000/api/rankings?country=England"

# Premier League teams only
curl "http://localhost:8000/api/rankings?league=Premier+League"

# Historical rankings on 2024-01-01
curl "http://localhost:8000/api/rankings?date=2024-01-01&limit=20"
```

---

### `GET /api/rankings/context`

Get a team's position in its domestic league ranking, plus 3 teams above and 3 below. Used to show a team's league context without loading the full rankings table.

**Tags:** Rankings

#### Request

##### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `team_id` | `integer` | Yes | -- | Team ID to center the ranking on |

#### Response

**Status:** `200 OK`

```json
{
  "team_id": 42,
  "league": "Premier League",
  "count": 7,
  "rankings": [
    {"rank": 3, "team": "Man City", "team_id": 38, "country": "England", "rating": 1720.5, "change_7d": 8.2},
    {"rank": 4, "team": "Liverpool", "team_id": 42, "country": "England", "rating": 1715.3, "change_7d": -2.1},
    {"rank": 5, "team": "Chelsea", "team_id": 61, "country": "England", "rating": 1693.7, "change_7d": 0.0}
  ]
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `team_id` | `integer` | Queried team ID |
| `league` | `string` | Domestic league name |
| `count` | `integer` | Number of teams returned (up to 7) |
| `rankings` | `array[RankingEntry]` | Surrounding teams in league ranking (same fields as `/api/rankings`) |

#### Errors

**404 Not Found:** Team not found, or no domestic league found for this team.

#### Example

```bash
curl "http://localhost:8000/api/rankings/context?team_id=42"
```

---

### `GET /api/teams/{team_id}`

Get detailed information about a specific team.

**Tags:** Teams

#### Request

##### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `team_id` | `integer` | Yes | Unique team identifier |

#### Response

**Status:** `200 OK`

```json
{
  "id": 17,
  "name": "Arsenal",
  "country": "England",
  "aliases": [],
  "current_rating": 1835.7,
  "rank": 2,
  "recent_matches": [
    {
      "date": "2026-03-09",
      "home_team": "Arsenal",
      "away_team": "Man United",
      "home_goals": 2,
      "away_goals": 0,
      "result": "H",
      "competition": "Premier League"
    }
  ]
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | `integer` | Team ID |
| `name` | `string` | Team canonical name |
| `country` | `string` | Country |
| `aliases` | `array[string]` | Alternative team names |
| `current_rating` | `number | null` | Current Elo rating |
| `rank` | `integer | null` | Current global ranking |
| `recent_matches` | `array` | Last 10 matches |
| `recent_matches[].date` | `string` | Match date (YYYY-MM-DD) |
| `recent_matches[].home_team` | `string` | Home team name |
| `recent_matches[].away_team` | `string` | Away team name |
| `recent_matches[].home_goals` | `integer` | Home team goals |
| `recent_matches[].away_goals` | `integer` | Away team goals |
| `recent_matches[].result` | `string` | Result: `"H"` (home win), `"D"` (draw), `"A"` (away win) |
| `recent_matches[].competition` | `string` | Competition name |

#### Errors

**404 Not Found:**
```json
{
  "error": "HTTPException",
  "message": "Team with ID 999 not found",
  "detail": null
}
```

#### Example

```bash
curl http://localhost:8000/api/teams/17
```

---

### `GET /api/teams/{team_id}/history`

Get full Elo rating trajectory for a team (for charting). Filtered by `display_from_date` (default: 2016-08-01) to exclude warm-up period.

**Tags:** Teams

#### Request

##### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `team_id` | `integer` | Yes | Unique team identifier |

##### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `limit` | `integer` | No | `500` | Maximum number of history points (1-2000) |

#### Response

**Status:** `200 OK`

```json
{
  "team": "Arsenal",
  "history": [
    {"date": "2016-08-14", "rating": 1500.0, "rating_delta": 0.0},
    {"date": "2016-08-21", "rating": 1512.5, "rating_delta": 12.5},
    {"date": "2016-08-28", "rating": 1523.8, "rating_delta": 11.3}
  ]
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `team` | `string` | Team name |
| `history` | `array` | Rating history points |
| `history[].date` | `string` | Match date (YYYY-MM-DD) |
| `history[].rating` | `number` | Elo rating after this match |
| `history[].rating_delta` | `number` | Change from previous rating |

#### Errors

**404 Not Found:** Team with given ID does not exist.

#### Example

```bash
# Full history (default 500 points)
curl http://localhost:8000/api/teams/17/history

# Last 100 matches
curl "http://localhost:8000/api/teams/17/history?limit=100"
```

---

### `GET /api/teams/{team_id}/results`

Get recent match results enriched with pre/post-match Elo ratings and a stats card including current rating, rank, form, 30-day trend, peak, and trough.

**Tags:** Teams

#### Request

##### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `team_id` | `integer` | Yes | Unique team identifier |

##### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `limit` | `integer` | No | `10` | Number of recent matches to return (1-50) |

#### Response

**Status:** `200 OK`

```json
{
  "team": "Arsenal",
  "stats": {
    "current_rating": 1835.7,
    "rank": 2,
    "form": ["W", "W", "D", "L", "W"],
    "trend_30d": 15.3,
    "peak_rating": 1860.0,
    "peak_date": "2025-12-01",
    "trough_rating": 1420.0,
    "trough_date": "2017-03-15"
  },
  "results": [
    {
      "date": "2026-03-09",
      "home_team": "Arsenal",
      "away_team": "Man United",
      "home_goals": 2,
      "away_goals": 0,
      "result": "H",
      "competition": "Premier League",
      "team_result": "W",
      "elo_before": 1823.2,
      "elo_after": 1835.7,
      "elo_change": 12.5
    }
  ]
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `team` | `string` | Team name |
| `stats` | `object` | Team statistics summary |
| `stats.current_rating` | `number` | Current Elo rating |
| `stats.rank` | `integer` | Current global rank |
| `stats.form` | `array[string]` | Last 5 results (`W`/`D`/`L`) |
| `stats.trend_30d` | `number` | Rating change over last 30 days |
| `stats.peak_rating` | `number` | All-time peak Elo rating (since display_from_date) |
| `stats.peak_date` | `string` | Date of peak rating (YYYY-MM-DD) |
| `stats.trough_rating` | `number` | All-time lowest Elo rating (since display_from_date) |
| `stats.trough_date` | `string` | Date of trough rating (YYYY-MM-DD) |
| `results` | `array` | Recent match results with Elo data |
| `results[].date` | `string` | Match date (YYYY-MM-DD) |
| `results[].home_team` | `string` | Home team name |
| `results[].away_team` | `string` | Away team name |
| `results[].home_goals` | `integer` | Home team goals |
| `results[].away_goals` | `integer` | Away team goals |
| `results[].result` | `string` | Match result (`H`/`D`/`A` from home perspective) |
| `results[].competition` | `string` | Competition name |
| `results[].team_result` | `string` | Result for this team (`W`/`D`/`L`) |
| `results[].elo_before` | `number` | Team Elo before match |
| `results[].elo_after` | `number` | Team Elo after match |
| `results[].elo_change` | `number` | Elo change from match |

#### Errors

**404 Not Found:** Team with given ID does not exist.

#### Example

```bash
# Last 10 results (default)
curl http://localhost:8000/api/teams/17/results

# Last 25 results
curl "http://localhost:8000/api/teams/17/results?limit=25"
```

---

### `GET /api/predict`

Predict match outcome probabilities based on current Elo ratings.

**Tags:** Predictions

#### Request

##### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `home` | `integer` | Yes | Home team ID |
| `away` | `integer` | Yes | Away team ID |

#### Response

**Status:** `200 OK`

```json
{
  "home_team": "Arsenal",
  "away_team": "Chelsea",
  "home_rating": 1835.7,
  "away_rating": 1693.7,
  "rating_diff": 142.0,
  "p_home": 0.6315,
  "p_draw": 0.1654,
  "p_away": 0.2030
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `home_team` | `string` | Home team name |
| `away_team` | `string` | Away team name |
| `home_rating` | `number` | Home team Elo rating |
| `away_rating` | `number` | Away team Elo rating |
| `rating_diff` | `number` | Rating difference (home - away) |
| `p_home` | `number` | Home win probability (0-1) |
| `p_draw` | `number` | Draw probability (0-1) |
| `p_away` | `number` | Away win probability (0-1) |

**Note:** `p_home + p_draw + p_away = 1.0`

#### Errors

**400 Bad Request (same team):**
```json
{
  "error": "HTTPException",
  "message": "Home and away teams must be different",
  "detail": null
}
```

**404 Not Found:**
```json
{
  "error": "HTTPException",
  "message": "Home team with ID 999 not found",
  "detail": null
}
```

#### Example

```bash
curl "http://localhost:8000/api/predict?home=17&away=61"
```

---

### `GET /api/leagues`

List all available leagues and competitions.

**Tags:** Leagues

#### Request

No parameters required.

#### Response

**Status:** `200 OK`

```json
{
  "count": 8,
  "leagues": [
    {"name": "Champions League", "country": "Europe", "tier": 1},
    {"name": "Europa League", "country": "Europe", "tier": 3},
    {"name": "Conference League", "country": "Europe", "tier": 4},
    {"name": "Premier League", "country": "England", "tier": 5},
    {"name": "La Liga", "country": "Spain", "tier": 5}
  ]
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `count` | `integer` | Number of leagues |
| `leagues` | `array` | List of league info |
| `leagues[].name` | `string` | Competition name |
| `leagues[].country` | `string` | Country or "Europe" |
| `leagues[].tier` | `integer` | Competition tier (1-5, lower is higher prestige) |

**Tier meanings:**
- `1`: Champions League knockout (1.5x K multiplier)
- `2`: Champions League group/league phase (1.2x K)
- `3`: Europa League knockout (1.2x K)
- `4`: Europa League group / Conference League (1.0x K)
- `5`: Domestic leagues (1.0x K baseline)

#### Example

```bash
curl http://localhost:8000/api/leagues
```

---

### `GET /api/search`

Full-text search for teams by name or alias.

**Tags:** Search

#### Request

##### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `q` | `string` | Yes | -- | Search query (min 1 character) |
| `limit` | `integer` | No | `10` | Maximum results (1-50) |

#### Response

**Status:** `200 OK`

```json
{
  "query": "bayern",
  "count": 1,
  "results": [
    {
      "id": 23,
      "name": "Bayern Munich",
      "country": "Germany",
      "aliases": ["FC Bayern München", "Bayern"]
    }
  ]
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `query` | `string` | Original search query |
| `count` | `integer` | Number of results |
| `results` | `array` | Search results |
| `results[].id` | `integer` | Team ID |
| `results[].name` | `string` | Team name |
| `results[].country` | `string` | Country |
| `results[].aliases` | `array[string]` | Alternative names |

**Search behavior:**
- Prefix matching enabled (e.g., "bay" matches "Bayern")
- Searches team names and aliases
- Results ranked by relevance (FTS5 ranking)

#### Examples

```bash
# Search for Bayern
curl "http://localhost:8000/api/search?q=bayern"

# Search for Arsenal, limit to 5 results
curl "http://localhost:8000/api/search?q=arsenal&limit=5"
```

---

### `GET /api/fixtures`

Get upcoming scheduled fixtures with Elo-based predictions.

**Tags:** Fixtures

#### Request

##### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `competition` | `string` | No | `null` | Filter by competition name (e.g., `Premier League`) |

#### Response

**Status:** `200 OK`

```json
{
  "count": 2,
  "fixtures": [
    {
      "date": "2026-03-22",
      "home_team": {"id": 17, "name": "Arsenal"},
      "away_team": {"id": 61, "name": "Chelsea"},
      "competition": "Premier League",
      "prediction": {
        "p_home": 0.5234,
        "p_draw": 0.2545,
        "p_away": 0.2221,
        "home_elo": 1835.7,
        "away_elo": 1693.7
      }
    }
  ]
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `count` | `integer` | Number of fixtures |
| `fixtures` | `array` | List of upcoming fixtures |
| `fixtures[].date` | `string` | Match date (YYYY-MM-DD) |
| `fixtures[].home_team` | `object` | Home team (`id`, `name`) |
| `fixtures[].away_team` | `object` | Away team (`id`, `name`) |
| `fixtures[].competition` | `string` | Competition name |
| `fixtures[].prediction` | `object | null` | Elo-based prediction (null if unavailable) |
| `fixtures[].prediction.p_home` | `number` | Home win probability (0-1) |
| `fixtures[].prediction.p_draw` | `number` | Draw probability (0-1) |
| `fixtures[].prediction.p_away` | `number` | Away win probability (0-1) |
| `fixtures[].prediction.home_elo` | `number` | Home team Elo at prediction time |
| `fixtures[].prediction.away_elo` | `number` | Away team Elo at prediction time |

#### Example

```bash
# All upcoming fixtures
curl http://localhost:8000/api/fixtures

# Premier League fixtures only
curl "http://localhost:8000/api/fixtures?competition=Premier+League"
```

---

### `GET /api/fixtures/scoped`

Get recent finished matches and upcoming fixtures for a given scope (country, competition, or team). Supports offset-based pagination for both finished and upcoming sections.

**Tags:** Fixtures

#### Request

##### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `country` | `string` | No | `null` | Filter by country (e.g., `England`) |
| `competition` | `string` | No | `null` | Filter by competition name (e.g., `Premier League`) |
| `team_id` | `integer` | No | `null` | Filter by team ID |
| `status` | `string` | No | `"both"` | Filter by status: `finished`, `scheduled`, or `both` |
| `limit` | `integer` | No | `3` | Max results per category (1-50) |
| `offset_finished` | `integer` | No | `0` | Offset for finished matches (skip N most recent) |
| `offset_upcoming` | `integer` | No | `0` | Offset for upcoming fixtures (skip N nearest) |

#### Response

**Status:** `200 OK`

```json
{
  "finished": [
    {
      "date": "2026-03-09",
      "home_team": {"id": 17, "name": "Arsenal"},
      "away_team": {"id": 38, "name": "Man United"},
      "competition": "Premier League",
      "status": "finished",
      "home_goals": 2,
      "away_goals": 0,
      "prediction": {
        "p_home": 0.62,
        "p_draw": 0.20,
        "p_away": 0.18,
        "home_elo": 1823.2,
        "away_elo": 1590.0
      },
      "competition_logo_url": "/static/logos/competitions/premier-league.svg"
    }
  ],
  "upcoming": [
    {
      "date": "2026-03-22",
      "home_team": {"id": 17, "name": "Arsenal"},
      "away_team": {"id": 61, "name": "Chelsea"},
      "competition": "Premier League",
      "status": "scheduled",
      "home_goals": null,
      "away_goals": null,
      "prediction": {
        "p_home": 0.52,
        "p_draw": 0.25,
        "p_away": 0.23,
        "home_elo": 1835.7,
        "away_elo": 1693.7
      },
      "competition_logo_url": "/static/logos/competitions/premier-league.svg"
    }
  ],
  "total_finished": 3,
  "total_upcoming": 3,
  "has_more_finished": true,
  "has_more_upcoming": true
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `finished` | `array` | Recent finished matches (chronological order) |
| `upcoming` | `array` | Upcoming scheduled fixtures |
| `total_finished` | `integer` | Count of finished matches returned |
| `total_upcoming` | `integer` | Count of upcoming fixtures returned |
| `has_more_finished` | `boolean` | Whether more older finished matches exist |
| `has_more_upcoming` | `boolean` | Whether more upcoming fixtures exist |

Each entry in `finished` and `upcoming` has:

| Field | Type | Description |
|-------|------|-------------|
| `date` | `string` | Match date (YYYY-MM-DD) |
| `home_team` | `object` | Home team (`id`, `name`) |
| `away_team` | `object` | Away team (`id`, `name`) |
| `competition` | `string` | Competition name |
| `status` | `string` | `"finished"` or `"scheduled"` |
| `home_goals` | `integer | null` | Home goals (null if upcoming) |
| `away_goals` | `integer | null` | Away goals (null if upcoming) |
| `prediction` | `object | null` | Elo-based prediction if available |
| `competition_logo_url` | `string | null` | URL for competition logo SVG |

#### Example

```bash
# All scoped fixtures (default 3+3)
curl http://localhost:8000/api/fixtures/scoped

# English fixtures
curl "http://localhost:8000/api/fixtures/scoped?country=England"

# Team fixtures with pagination
curl "http://localhost:8000/api/fixtures/scoped?team_id=42&limit=5&offset_finished=5"
```

---

### `GET /api/chart/scoped`

Get rating history for top N teams in a scope (country, competition, or single team). Used to render Elo charts.

**Tags:** Charts

#### Request

##### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `country` | `string` | No | `null` | Filter by country |
| `competition` | `string` | No | `null` | Filter by competition name |
| `team_id` | `integer` | No | `null` | Single team ID (overrides country/competition) |
| `top_n` | `integer` | No | `5` | Number of top teams to return (1-20) |

**Scoping logic:**
- If `team_id` given: returns that single team's history.
- If `competition` given: returns top N teams by current Elo in that league.
- If `country` given: returns top N teams by current Elo in that country.
- Otherwise: returns global top N.

#### Response

**Status:** `200 OK`

```json
{
  "teams": [
    {
      "team_id": 17,
      "team": "Arsenal",
      "history": [
        {"date": "2016-08-14", "rating": 1500.0, "rating_delta": 0.0},
        {"date": "2016-08-21", "rating": 1512.5, "rating_delta": 12.5}
      ]
    }
  ],
  "count": 1
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `teams` | `array` | Rating histories for teams in scope |
| `teams[].team_id` | `integer` | Team ID |
| `teams[].team` | `string` | Team name |
| `teams[].history` | `array` | Rating history points (date, rating, rating_delta) |
| `count` | `integer` | Number of teams returned |

#### Example

```bash
# Global top 5
curl http://localhost:8000/api/chart/scoped

# Top 3 in Premier League
curl "http://localhost:8000/api/chart/scoped?competition=Premier+League&top_n=3"

# Single team
curl "http://localhost:8000/api/chart/scoped?team_id=42"
```

---

### `GET /api/sidebar`

Get the navigation tree for the sidebar. Returns nations grouped with their domestic competitions (with flag URLs) and European club competitions (with logo URLs). Response is cached in-memory for 1 hour.

**Tags:** Navigation

#### Request

No parameters required.

#### Response

**Status:** `200 OK`

```json
{
  "nations": [
    {
      "country": "England",
      "flag_url": "/static/flags/england.svg",
      "competitions": [
        {
          "id": 1,
          "name": "Premier League",
          "type": "league",
          "logo_url": "/static/logos/competitions/premier-league.svg"
        }
      ]
    }
  ],
  "european": [
    {
      "id": 6,
      "name": "Champions League",
      "type": "cup",
      "logo_url": "/static/logos/competitions/champions-league.svg"
    }
  ]
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `nations` | `array` | Nations with their domestic competitions |
| `nations[].country` | `string` | Country name |
| `nations[].flag_url` | `string | null` | URL for country flag SVG |
| `nations[].competitions` | `array` | Competitions in this country |
| `nations[].competitions[].id` | `integer` | Competition ID |
| `nations[].competitions[].name` | `string` | Competition name |
| `nations[].competitions[].type` | `string` | `"league"` or `"cup"` |
| `nations[].competitions[].logo_url` | `string | null` | URL for competition logo SVG |
| `european` | `array` | European club competitions (same structure as competitions) |

#### Example

```bash
curl http://localhost:8000/api/sidebar
```

---

### `GET /api/prediction-accuracy`

Aggregate prediction accuracy statistics including Brier scores, calibration data, per-competition breakdown, per-source breakdown, recent form, and rolling time series.

**Tags:** Predictions

#### Request

##### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `competition` | `string` | No | `null` | Filter by competition name (e.g., `Premier League`) |
| `source` | `string` | No | `null` | Filter by prediction source (`live` or `backfill`) |
| `country` | `string` | No | `null` | Filter by country name (e.g., `England`) |
| `team_id` | `integer` | No | `null` | Filter by team ID |

#### Response

**Status:** `200 OK`

```json
{
  "total_predictions": 20263,
  "mean_brier_score": 0.5860,
  "median_brier_score": 0.5200,
  "calibration": {
    "0-10": {"count": 500, "actual_frequency": 0.06, "expected_midpoint": 0.05},
    "10-20": {"count": 800, "actual_frequency": 0.14, "expected_midpoint": 0.15}
  },
  "by_competition": {
    "Premier League": {"count": 3800, "mean_brier_score": 0.5700},
    "Champions League": {"count": 500, "mean_brier_score": 0.6100}
  },
  "by_source": {
    "live": {"count": 263, "mean_brier_score": 0.5500},
    "backfill": {"count": 20000, "mean_brier_score": 0.5870}
  },
  "recent_form": 0.4200,
  "time_series": [
    {"date": "2026-03-01", "rolling_brier": 0.42, "count": 50}
  ]
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `total_predictions` | `integer` | Total number of scored predictions |
| `mean_brier_score` | `number | null` | Mean Brier score (lower is better, 0=perfect, 2=worst) |
| `median_brier_score` | `number | null` | Median Brier score |
| `calibration` | `object` | Calibration data by probability bucket |
| `by_competition` | `object` | Brier score breakdown by competition name |
| `by_source` | `object` | Brier score breakdown by prediction source (`live` vs `backfill`) |
| `recent_form` | `number | null` | Mean Brier score over the last 100 predictions |
| `time_series` | `array` | Rolling Brier score time series for trend chart |

#### Example

```bash
# Global accuracy
curl http://localhost:8000/api/prediction-accuracy

# Live predictions only
curl "http://localhost:8000/api/prediction-accuracy?source=live"

# English competitions
curl "http://localhost:8000/api/prediction-accuracy?country=England"

# Specific team
curl "http://localhost:8000/api/prediction-accuracy?team_id=42"
```

---

### `GET /api/prediction-history`

Paginated list of scored predictions with match details, probabilities, and Brier scores. Supports filtering by competition, date range, source, team name search, country, and team ID.

**Tags:** Predictions

#### Request

##### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `page` | `integer` | No | `1` | Page number (1-indexed) |
| `per_page` | `integer` | No | `20` | Items per page (1-100) |
| `competition` | `string` | No | `null` | Filter by competition name |
| `date_from` | `string` | No | `null` | Filter from date, inclusive (YYYY-MM-DD) |
| `date_to` | `string` | No | `null` | Filter to date, inclusive (YYYY-MM-DD) |
| `source` | `string` | No | `null` | Filter by prediction source (`live` or `backfill`) |
| `search` | `string` | No | `null` | Search by team name (whitespace-separated tokens, all must match) |
| `country` | `string` | No | `null` | Filter by country name |
| `team_id` | `integer` | No | `null` | Filter by team ID |

#### Response

**Status:** `200 OK`

```json
{
  "items": [
    {
      "date": "2026-03-15",
      "home_team": "Arsenal",
      "away_team": "Chelsea",
      "competition": "Premier League",
      "p_home": 0.52,
      "p_draw": 0.25,
      "p_away": 0.23,
      "actual_result": "H",
      "home_goals": 2,
      "away_goals": 1,
      "brier_score": 0.35,
      "home_elo": 1836.0,
      "away_elo": 1650.0,
      "source": "live"
    }
  ],
  "total": 150,
  "page": 1,
  "per_page": 20,
  "pages": 8
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `items` | `array` | List of scored predictions |
| `items[].date` | `string` | Match date (YYYY-MM-DD) |
| `items[].home_team` | `string` | Home team name |
| `items[].away_team` | `string` | Away team name |
| `items[].competition` | `string` | Competition name |
| `items[].p_home` | `number` | Predicted home win probability |
| `items[].p_draw` | `number` | Predicted draw probability |
| `items[].p_away` | `number` | Predicted away win probability |
| `items[].actual_result` | `string` | Actual match result (`H`/`D`/`A`) |
| `items[].home_goals` | `integer` | Home team goals scored |
| `items[].away_goals` | `integer` | Away team goals scored |
| `items[].brier_score` | `number` | Brier score for this prediction |
| `items[].home_elo` | `number` | Home team Elo at prediction time |
| `items[].away_elo` | `number` | Away team Elo at prediction time |
| `items[].source` | `string` | Prediction source (`live` or `backfill`) |
| `total` | `integer` | Total matching predictions |
| `page` | `integer` | Current page number |
| `per_page` | `integer` | Items per page |
| `pages` | `integer` | Total number of pages |

#### Example

```bash
# Default page 1
curl http://localhost:8000/api/prediction-history

# Search for Liverpool matches
curl "http://localhost:8000/api/prediction-history?search=Liverpool"

# Live predictions in 2026
curl "http://localhost:8000/api/prediction-history?source=live&date_from=2026-01-01"

# Page 3 with 50 items
curl "http://localhost:8000/api/prediction-history?page=3&per_page=50"
```

---

### `GET /api/accuracy/scoped`

Compact prediction accuracy stats scoped to country, competition, or team. Returns accuracy percentage, mean Brier score, and trend vs previous period.

**Tags:** Predictions

#### Request

##### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `country` | `string` | No | `null` | Filter by country |
| `competition` | `string` | No | `null` | Filter by competition name |
| `team_id` | `integer` | No | `null` | Filter by team ID |

#### Response

**Status:** `200 OK`

```json
{
  "total_predictions": 120,
  "accuracy_pct": 52.3,
  "mean_brier_score": 0.4321,
  "trend_pct": 1.5
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `total_predictions` | `integer` | Number of scored predictions in scope |
| `accuracy_pct` | `number | null` | Percentage of correct outcome predictions (0-100) |
| `mean_brier_score` | `number | null` | Mean Brier score (lower is better) |
| `trend_pct` | `number | null` | Accuracy change vs previous period (percentage points). Computed by comparing second-half vs first-half accuracy. |

#### Example

```bash
# Global accuracy
curl http://localhost:8000/api/accuracy/scoped

# English competitions
curl "http://localhost:8000/api/accuracy/scoped?country=England"

# Specific team
curl "http://localhost:8000/api/accuracy/scoped?team_id=42"
```

---

### `GET /api/accuracy/grid`

3x3 prediction performance grid (confusion matrix) of predicted vs actual outcomes, with counts and percentages. Supports the same scoping as `/api/accuracy/scoped`, plus source filtering.

**Tags:** Predictions

#### Request

##### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `country` | `string` | No | `null` | Filter by country |
| `competition` | `string` | No | `null` | Filter by competition name |
| `team_id` | `integer` | No | `null` | Filter by team ID |
| `source` | `string` | No | `null` | Filter by prediction source (`live` or `backfill`) |

#### Response

**Status:** `200 OK`

```json
{
  "actual_home": {
    "predicted_home": {"count": 5200, "pct_of_row": 65.0, "pct_of_total": 25.7},
    "predicted_draw": {"count": 800, "pct_of_row": 10.0, "pct_of_total": 3.9},
    "predicted_away": {"count": 2000, "pct_of_row": 25.0, "pct_of_total": 9.9},
    "total": 8000
  },
  "actual_draw": {
    "predicted_home": {"count": 2400, "pct_of_row": 45.3, "pct_of_total": 11.8},
    "predicted_draw": {"count": 1363, "pct_of_row": 25.7, "pct_of_total": 6.7},
    "predicted_away": {"count": 1537, "pct_of_row": 29.0, "pct_of_total": 7.6},
    "total": 5300
  },
  "actual_away": {
    "predicted_home": {"count": 1500, "pct_of_row": 21.6, "pct_of_total": 7.4},
    "predicted_draw": {"count": 463, "pct_of_row": 6.6, "pct_of_total": 2.3},
    "predicted_away": {"count": 5000, "pct_of_row": 71.8, "pct_of_total": 24.7},
    "total": 6963
  },
  "total": 20263,
  "correct": 11563,
  "accuracy_pct": 57.1
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `actual_home` | `object` | Row for actual Home wins |
| `actual_draw` | `object` | Row for actual Draws |
| `actual_away` | `object` | Row for actual Away wins |
| `total` | `integer` | Grand total of all scored predictions |
| `correct` | `integer` | Number of correct predictions (diagonal sum) |
| `accuracy_pct` | `number` | Overall accuracy percentage (0-100) |

Each row contains:

| Field | Type | Description |
|-------|------|-------------|
| `predicted_home` | `object` | Cell where predicted outcome is Home |
| `predicted_draw` | `object` | Cell where predicted outcome is Draw |
| `predicted_away` | `object` | Cell where predicted outcome is Away |
| `total` | `integer` | Row total (all matches with this actual outcome) |

Each cell contains:

| Field | Type | Description |
|-------|------|-------------|
| `count` | `integer` | Number of matches in this cell |
| `pct_of_row` | `number` | Percentage of the actual outcome row (0-100) |
| `pct_of_total` | `number` | Percentage of all predictions (0-100) |

#### Example

```bash
# Global grid
curl http://localhost:8000/api/accuracy/grid

# Live predictions only
curl "http://localhost:8000/api/accuracy/grid?source=live"

# Premier League
curl "http://localhost:8000/api/accuracy/grid?competition=Premier+League"
```

---

## Pagination Conventions

**Endpoints with pagination:**
- `/api/rankings` -- simple `limit` (1-500, default 50)
- `/api/teams/{id}/history` -- simple `limit` (1-2000, default 500)
- `/api/teams/{id}/results` -- simple `limit` (1-50, default 10)
- `/api/fixtures/scoped` -- dual offset-based: `limit`, `offset_finished`, `offset_upcoming` with `has_more_*` indicators
- `/api/prediction-history` -- page-based: `page`, `per_page` (1-100), returns `total`, `pages`
- `/api/chart/scoped` -- `top_n` (1-20, default 5)

---

## Filtering & Sorting

**Available filters:**
- `/api/rankings` -- `date`, `country`, `league`
- `/api/fixtures` -- `competition`
- `/api/fixtures/scoped` -- `country`, `competition`, `team_id`, `status`
- `/api/chart/scoped` -- `country`, `competition`, `team_id`
- `/api/accuracy/scoped` -- `country`, `competition`, `team_id`
- `/api/accuracy/grid` -- `country`, `competition`, `team_id`, `source`
- `/api/prediction-accuracy` -- `competition`, `source`, `country`, `team_id`
- `/api/prediction-history` -- `competition`, `source`, `country`, `team_id`, `date_from`, `date_to`, `search`
- `/api/search` -- `q` (text search)

**Sorting:** Results are pre-sorted by relevance:
- Rankings: rating DESC
- History: date ASC
- Finished matches: date DESC
- Upcoming fixtures: date ASC
- Predictions: scored_at ASC
- Search: FTS5 rank

---

## OpenAPI Specification

The API provides auto-generated OpenAPI 3.0 documentation:

- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`
- **OpenAPI JSON:** `http://localhost:8000/openapi.json`

---

## Example Responses

All example responses are available as JSON files in `docs/api-examples/`:

- `health.json` -- Health check
- `rankings-current.json` -- Current rankings
- `rankings-historical.json` -- Historical rankings
- `team-detail.json` -- Team detail page
- `team-history.json` -- Team rating trajectory
- `prediction.json` -- Match prediction
- `search.json` -- Team search results
- `leagues.json` -- Leagues list
- `error-404.json` -- Not found error
- `error-400.json` -- Bad request error

---

## Client Libraries

**Current version:** No official client libraries.

**Future versions:** May provide TypeScript/Python SDKs.

**Community clients:** Developers can generate clients from the OpenAPI spec using tools like:
- [OpenAPI Generator](https://openapi-generator.tech/)
- [Swagger Codegen](https://swagger.io/tools/swagger-codegen/)

---

## Changelog

### v2.0.0 (2026-03-19)
- Updated API contract documentation to cover all 17 endpoints (was 7)
- Updated data coverage: 325 teams, 31,789 matches (2010-2026)

### v1.5.0 -- Sprint 15 (2026-03-18)
- Added `GET /api/accuracy/grid` -- 3x3 prediction performance grid (confusion matrix)
- Extended `/api/prediction-accuracy` with `country` and `team_id` filters
- Extended `/api/prediction-history` with `country`, `team_id`, and `search` filters

### v1.4.0 -- Sprint 14 (2026-03-17)
- Added `source` column to predictions (`live` vs `backfill`)
- Added `by_source` breakdown to `/api/prediction-accuracy`
- Added `source` field to `/api/prediction-history` items
- Historical backfill: 20,263 predictions with pre-match Elo ratings

### v1.3.0 -- Sprint 13 (2026-03-16)
- Added `flag_url` to `SidebarNation` in `/api/sidebar`
- Added `logo_url` to `SidebarCompetition` in `/api/sidebar`
- Added `competition_logo_url` to `ScopedFixtureEntry` in `/api/fixtures/scoped`
- SVG flags for 6 countries and 8 competition badge logos

### v1.2.0 -- Sprint 12 (2026-03-14)
- Added `GET /api/sidebar` -- navigation tree with nations and competitions
- Added `GET /api/rankings/context` -- team-context rankings (team +/- 3 neighbors)
- Added `GET /api/fixtures/scoped` -- scoped fixtures with offset pagination
- Added `GET /api/chart/scoped` -- scoped chart data for top N teams
- Added `GET /api/accuracy/scoped` -- compact accuracy stats by scope
- Unified single-page layout; old route redirects added

### v1.1.0 -- Sprint 10 (2026-03-13)
- Added `GET /api/fixtures` -- upcoming fixtures with Elo predictions
- Added `GET /api/prediction-accuracy` -- aggregate accuracy stats with Brier scores
- Added `GET /api/prediction-history` -- paginated scored prediction log
- Schema migration system, incremental update pipeline
- football-data.org live data integration

### v1.0.1 -- Sprint 8 (2026-03-13)
- Added `GET /api/teams/{team_id}/results` -- team match results with Elo data and stats card
- Added `country`, `league` query parameters to `GET /api/rankings`
- Added `change_7d` and `team_id` fields to ranking entries

### v1.0.0 (2026-03-13)
- Initial release
- 7 endpoints: health, rankings, teams, history, predict, leagues, search
- Full-text search using SQLite FTS5
- OpenAPI 3.0 documentation

---

## Support

For issues, feature requests, or questions:
- GitHub Issues: (URL TBD)
- Email: (contact TBD)
