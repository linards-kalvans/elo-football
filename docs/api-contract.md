# Football Elo Rating API Contract

**Version:** 1.0.0
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
  - [Team Detail](#get-apiteamsteam_id)
  - [Team History](#get-apiteamsteam_idhistory)
  - [Match Prediction](#get-apipredict)
  - [Leagues](#get-apileagues)
  - [Team Search](#get-apisearch)

---

## Overview

The Football Elo Rating API provides access to Elo ratings for 300 European football clubs across 5 domestic leagues and European competitions (Champions League, Europa League, Conference League).

**Data coverage:**
- **Teams:** 300
- **Matches:** 20,833 (2015-2026)
- **Leagues:** Premier League, La Liga, Bundesliga, Serie A, Ligue 1
- **European Competitions:** Champions League, Europa League, Conference League

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
  "detail": "Optional additional details"
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

**Production:** CORS should be restricted to specific domains.

```
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, OPTIONS
Access-Control-Allow-Headers: *
```

---

## Endpoints

---

### `GET /api/health`

Health check endpoint — verifies API and database connectivity.

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
  "total_teams": 300,
  "total_matches": 20833,
  "latest_match_date": "2026-03-09"
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

Get current or historical Elo rankings.

**Tags:** Rankings

#### Request

##### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `date` | `string` | No | `null` | Date for historical rankings (YYYY-MM-DD). Omit for current rankings. |
| `limit` | `integer` | No | `50` | Maximum number of teams to return (1-500) |

#### Response

**Status:** `200 OK`

**Current rankings (`date=null`):**
```json
{
  "date": null,
  "count": 10,
  "rankings": [
    {"rank": 1, "team": "Bayern Munich", "country": "Germany", "rating": 1835.9},
    {"rank": 2, "team": "Arsenal", "country": "England", "rating": 1835.7},
    {"rank": 3, "team": "Barcelona", "country": "Spain", "rating": 1757.1}
  ]
}
```

**Historical rankings (`date=2024-01-01`):**
```json
{
  "date": "2024-01-01",
  "count": 5,
  "rankings": [
    {"rank": 1, "team": "Man City", "country": "England", "rating": 1778.2},
    {"rank": 2, "team": "Arsenal", "country": "England", "rating": 1751.3}
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
| `rankings[].country` | `string` | Team country |
| `rankings[].rating` | `number` | Elo rating |

#### Examples

```bash
# Current rankings (top 50)
curl http://localhost:8000/api/rankings

# Current top 10
curl "http://localhost:8000/api/rankings?limit=10"

# Historical rankings on 2024-01-01
curl "http://localhost:8000/api/rankings?date=2024-01-01&limit=20"
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

#### Examples

```bash
curl http://localhost:8000/api/teams/17
```

---

### `GET /api/teams/{team_id}/history`

Get full Elo rating trajectory for a team (for charting).

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
    {"date": "2015-08-09", "rating": 1500.0, "rating_delta": 0.0},
    {"date": "2015-08-16", "rating": 1512.5, "rating_delta": 12.5},
    {"date": "2015-08-23", "rating": 1523.8, "rating_delta": 11.3}
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

**404 Not Found:**
```json
{
  "error": "HTTPException",
  "message": "Team with ID 999 not found",
  "detail": null
}
```

#### Examples

```bash
# Full history (default 500 points)
curl http://localhost:8000/api/teams/17/history

# Last 100 matches
curl "http://localhost:8000/api/teams/17/history?limit=100"
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
  "message": "One or both teams not found (IDs: 17, 999)",
  "detail": null
}
```

#### Examples

```bash
# Arsenal vs Chelsea
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
- `1`: Champions League knockout
- `3`: Europa League knockout
- `4`: Conference League / Europa League group
- `5`: Domestic leagues

#### Examples

```bash
curl http://localhost:8000/api/leagues
```

---

### `GET /api/search`

Full-text search for teams by name or alias.

**Tags:** Search

#### Request

##### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `q` | `string` | Yes | Search query (min 1 character) |
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

## OpenAPI Specification

The API provides auto-generated OpenAPI 3.0 documentation:

- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`
- **OpenAPI JSON:** `http://localhost:8000/openapi.json`

---

## Pagination Conventions

**Current version:** Simple limit-based pagination.

**Query parameters:**
- `limit`: Maximum number of results (varies by endpoint)
- `offset`: Not yet implemented

**Future versions:** May add offset or cursor-based pagination for large result sets.

---

## Filtering & Sorting

**Current version:** Limited filtering.

**Available filters:**
- `/api/rankings?date=YYYY-MM-DD` — Historical date filter
- `/api/search?q=query` — Text search

**Future versions:** May add filters for:
- Country (e.g., `/api/rankings?country=England`)
- League (e.g., `/api/teams?league=Premier+League`)
- Date ranges (e.g., `/api/teams/{id}/history?from=2024-01-01&to=2024-12-31`)

**Sorting:** Results are pre-sorted by relevance (ratings DESC for rankings, date ASC for history).

---

## Example Responses

All example responses are available as JSON files in `docs/api-examples/`:

- `health.json` — Health check
- `rankings-current.json` — Current rankings
- `rankings-historical.json` — Historical rankings
- `team-detail.json` — Team detail page
- `team-history.json` — Team rating trajectory
- `prediction.json` — Match prediction
- `search.json` — Team search results
- `leagues.json` — Leagues list
- `error-404.json` — Not found error
- `error-400.json` — Bad request error

---

## Client Libraries

**Current version:** No official client libraries.

**Future versions:** May provide TypeScript/Python SDKs.

**Community clients:** Developers can generate clients from the OpenAPI spec using tools like:
- [OpenAPI Generator](https://openapi-generator.tech/)
- [Swagger Codegen](https://swagger.io/tools/swagger-codegen/)

---

## Changelog

### v1.0.0 (2026-03-13)
- Initial release
- 8 endpoints: health, rankings, teams, history, predict, leagues, search
- Full-text search using SQLite FTS5
- OpenAPI 3.0 documentation

---

## Support

For issues, feature requests, or questions:
- GitHub Issues: (URL TBD)
- Email: (contact TBD)
