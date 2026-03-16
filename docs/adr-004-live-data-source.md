# ADR-004: Live Data Source Selection

**Status:** DECIDED
**Date:** 2026-03-15
**Deciders:** Product Team
**Context:** Sprint 9 — Live data integration for match fixtures and results

---

## Context

The Football Elo Rating web application currently uses historical static data from two sources:

- **Domestic leagues** (5 leagues): Football-Data.co.uk CSVs (manual download)
- **European competitions** (CL/EL/Conference): openfootball .txt files (manual download)

This static approach covers 31,789 historical matches but has critical limitations:

1. **Stale ratings** — No mechanism to update Elo ratings after new matches
2. **No fixtures** — Cannot display upcoming matches or predict future probabilities
3. **Manual effort** — Data refresh requires manual CSV downloads and re-running pipeline
4. **User expectations** — A public-facing web app needs current ratings (updated within 24-48 hours of matches)

Sprint 9 introduces **quasi-live data** to address these gaps. The goal is to automate match result ingestion and display upcoming fixtures.

## Requirements

### Coverage

Must support all competitions currently in scope:

- **Domestic leagues** (5): Premier League, La Liga, Bundesliga, Serie A, Ligue 1
- **European competitions** (3): Champions League, Europa League, Conference League

### Data Freshness

- **Match results**: Updated within 24 hours of match completion (tolerable delay for Elo recalculation)
- **Fixtures**: Upcoming matches available at least 1 week in advance

### Rate Limits

- **Batch updates**: 1-2 full ingestions per day (morning + evening)
- **Per-batch request volume**: ~50-100 API calls (8 competitions × ~5-15 requests each for paginated results/fixtures)

### Cost Constraints

- **Budget**: $0-$50/year (hobby/open-source project)
- **Preference**: Free tier if adequate

---

## Options Evaluated

### 1. football-data.org (RECOMMENDED)

**Overview:** Free football data API maintained by Daniel Freitag since 2015. Provides structured JSON endpoints for European football leagues and competitions.

#### Pricing & Rate Limits

| Tier | Cost | Rate Limit | Restrictions |
|------|------|------------|--------------|
| **Free** | $0 | 10 calls/min | Limited competitions (excludes some tier-2 leagues) |
| Tier 1 | €14.99/month | 50 calls/min | All competitions, no ads |
| Tier 2 | €49.99/month | 100 calls/min | Premium data (lineups, odds) |

**Free tier details:**
- 10 requests per minute
- Access to top-tier European leagues + Champions League, Europa League, Conference League
- Historical data (2-3 seasons back)

#### Coverage

| Competition | Available | API ID |
|------------|-----------|--------|
| Premier League | Yes | `PL` |
| La Liga | Yes | `PD` |
| Bundesliga | Yes | `BL1` |
| Serie A | Yes | `SA` |
| Ligue 1 | Yes | `FL1` |
| Champions League | Yes | `CL` |
| Europa League | Yes | `EL` |
| Conference League | Yes | `EC` |

**Perfect alignment** — all 8 required competitions supported in free tier.

#### API Quality

- **Authentication:** API key (simple header: `X-Auth-Token`)
- **Response format:** Well-structured JSON with consistent schema
- **Team identifiers:** Stable team IDs (no name-matching required)
- **Documentation:** Excellent (OpenAPI spec, examples, migration guides)
- **Endpoints:**
  - `/competitions/{id}/matches` — All matches (results + fixtures)
  - `/competitions/{id}/standings` — League tables
  - `/teams/{id}` — Team metadata

#### Integration Complexity

**Low complexity** — clean REST API with predictable pagination.

**Estimated implementation effort:** ~12 hours
- Team ID mapping to existing `teams` table: 4 hours (one-time)
- API client with rate limiting: 2 hours
- Match ingestion pipeline: 4 hours
- Fixture display endpoint: 2 hours

**Rate limit management:**
- 10 calls/min = 600 calls/hour
- Our batch update (~80 calls) fits in **8 minutes**
- No rate limit risk with 2 updates/day

---

### 2. API-Football (RapidAPI)

**Overview:** Comprehensive football data API hosted on RapidAPI. Extensive coverage (1000+ leagues) but restrictive free tier.

#### Pricing & Rate Limits

| Tier | Cost | Rate Limit | Daily Quota |
|------|------|------------|-------------|
| **Free** | $0 | 10 calls/min | **100 calls/day** |
| Basic | $9.99/month | 300 calls/min | 10,000 calls/day |

**Free tier bottleneck:**
- **100 calls/day** is insufficient for our needs
- 8 competitions × ~10 calls each = **80 calls per batch**
- 2 batches/day = **160 calls/day** — exceeds free tier by 60%
- Would require **Basic plan ($10/month = $120/year)** — over budget

#### Coverage

All 8 competitions supported. Full coverage.

#### Pros & Cons

- Faster data freshness (<1 hour vs 1-2 hours)
- Rich metadata (statistics, lineups, odds)
- **Free tier insufficient** — 100 calls/day blocks our use case
- **Requires paid plan** ($120/year exceeds budget)
- RapidAPI dependency — vendor lock-in

---

### 3. TheSportsDB

**Overview:** Free, community-driven sports data API with broad coverage but limited reliability.

#### Pricing & Rate Limits

| Tier | Cost | Rate Limit |
|------|------|------------|
| **Free** | $0 | 30 calls/min |
| Patreon | $3+/month | Higher limits |

#### Coverage Issues

- Europa League: Limited/unreliable
- **Conference League: Not available**
- Only 6/8 competitions supported (75%)

#### Key Problems

- **24-72 hour data lag** — defeats purpose of "live" data
- **Community-sourced** — prone to errors and missing matches
- **Poor documentation** — minimal examples, inconsistent schema
- **High maintenance burden** — requires constant validation

---

## Decision

**Selected API:** **football-data.org (Free tier)**

### Comparison Matrix

| Criterion | football-data.org | API-Football | TheSportsDB |
|-----------|------------------|--------------|-------------|
| **Cost (free tier)** | $0 (adequate) | $0 (insufficient) | $0 |
| **Coverage (8/8)** | 100% | 100% | 75% |
| **Rate limits** | Adequate | Needs paid | High |
| **Data freshness** | 1-2 hours | <1 hour | 24-72 hours |
| **Data reliability** | High | High | Low |
| **Documentation** | Excellent | Good | Poor |
| **Integration effort** | Low (12h) | Medium (15h) | High (21h) |
| **Overall fit** | **Excellent** | Over-budget | Unreliable |

### Rationale

1. **Cost:** $0/year (fits hobby/open-source budget)
2. **Coverage:** 8/8 competitions supported (100% match)
3. **Rate limits:** 10 calls/min sufficient for 80-call batches
4. **Data quality:** High reliability, stable team IDs, consistent schema
5. **Integration complexity:** Low (~12 hours implementation)
6. **Track record:** 9 years in operation, active community

---

## Implementation Plan (Sprint 10)

### Phase 1: API Client

```python
# src/live/football_data_client.py
class FootballDataAPI:
    BASE_URL = "https://api.football-data.org/v4"

    def __init__(self, api_key: str):
        self.headers = {"X-Auth-Token": api_key}

    async def get_matches(self, competition_code: str, date_from: str, date_to: str):
        """Fetch matches for a competition within date range."""
        ...
```

### Phase 2: Team ID Mapping

One-time mapping of football-data.org team IDs to existing `teams` table (300 teams).

### Phase 3: Scheduled Ingestion

Cron job or systemd timer (2x daily: 6am, 6pm) to fetch recent matches and upcoming fixtures.

### Phase 4: Fixtures Frontend

Add "Upcoming Matches" section using new `fixtures` table.

---

## Cost Analysis

**Annual API usage projection:**
- 2 batches/day × 80 calls/batch × 365 days = **58,400 calls/year**
- football-data.org free tier: **10 calls/min = 5.26M calls/year capacity**
- **Utilization:** 1.1% of free tier capacity

**Conclusion:** Free tier is sustainable indefinitely with massive headroom.

---

## Consequences

### Positive

- Zero cost — Free tier covers all current needs
- Low maintenance — Stable API with consistent schema
- Reliable data — High-quality official sources
- Simple integration — Clean REST API, well-documented

### Negative

- Rate limit awareness — Must implement exponential backoff (10 calls/min)
- Single-source dependency — No fallback if API goes down
- Free tier restrictions — Expansion beyond top-5 + European requires paid tier

---

## References

- [football-data.org API Documentation](https://www.football-data.org/documentation/quickstart)
- [football-data.org Pricing](https://www.football-data.org/pricing)
- [API-Football RapidAPI](https://rapidapi.com/api-sports/api/api-football)
- [TheSportsDB Documentation](https://www.thesportsdb.com/api.php)
