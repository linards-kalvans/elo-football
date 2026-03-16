"""Async client for football-data.org API v4.

Provides rate-limited, retry-aware access to match data, team info,
and competition rosters for live data ingestion.

Auth: Set FOOTBALL_DATA_API_KEY environment variable.
Free tier limit: 10 requests/minute.
"""

import asyncio
import os
import time

import httpx


# ---------------------------------------------------------------------------
# Competition code mapping (football-data.org codes)
# ---------------------------------------------------------------------------
COMPETITION_MAP = {
    "PL": {"name": "Premier League", "country": "England", "tier": 5},
    "PD": {"name": "La Liga", "country": "Spain", "tier": 5},
    "BL1": {"name": "Bundesliga", "country": "Germany", "tier": 5},
    "SA": {"name": "Serie A", "country": "Italy", "tier": 5},
    "FL1": {"name": "Ligue 1", "country": "France", "tier": 5},
    "CL": {"name": "Champions League", "country": "", "tier": 1},
    "EL": {"name": "Europa League", "country": "", "tier": 3},
    "EC": {"name": "Conference League", "country": "", "tier": 4},
}

BASE_URL = "https://api.football-data.org/v4"
MAX_RETRIES = 3
RATE_LIMIT = 10  # requests per minute


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class ApiError(Exception):
    """General API error."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"API error {status_code}: {message}")


class RateLimitError(ApiError):
    """429 Too Many Requests."""

    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(429, message)


class AuthError(ApiError):
    """401/403 authentication failure."""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(401, message)


# ---------------------------------------------------------------------------
# Rate limiter (token bucket, 10 tokens per 60 seconds)
# ---------------------------------------------------------------------------
class _RateLimiter:
    """Simple token-bucket rate limiter for 10 requests/minute."""

    def __init__(self, max_tokens: int = RATE_LIMIT, interval: float = 60.0):
        self.max_tokens = max_tokens
        self.interval = interval
        # Start with fewer tokens to avoid initial burst that triggers 429s
        self.tokens = min(3, max_tokens)
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()
        # Minimum delay between requests (6.5s for 10/min with safety margin)
        self._min_delay = interval / max_tokens + 0.5
        self._last_request = 0.0

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_refill
        new_tokens = elapsed * (self.max_tokens / self.interval)
        self.tokens = min(self.max_tokens, self.tokens + new_tokens)
        self.last_refill = now

    async def acquire(self) -> None:
        """Wait until a token is available, then consume one."""
        async with self._lock:
            # Enforce minimum delay between requests
            now = time.monotonic()
            since_last = now - self._last_request
            if since_last < self._min_delay:
                await asyncio.sleep(self._min_delay - since_last)

            self._refill()
            while self.tokens < 1:
                wait = (1 - self.tokens) * (self.interval / self.max_tokens)
                await asyncio.sleep(wait)
                self._refill()
            self.tokens -= 1
            self._last_request = time.monotonic()


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------
class FootballDataClient:
    """Async client for football-data.org API v4."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("FOOTBALL_DATA_API_KEY")
        if not self.api_key:
            raise AuthError(
                "FOOTBALL_DATA_API_KEY not set. "
                "Get a free key at https://www.football-data.org/client/register"
            )
        self._client: httpx.AsyncClient | None = None
        self._rate_limiter = _RateLimiter()

    async def __aenter__(self) -> "FootballDataClient":
        self._client = httpx.AsyncClient(
            base_url=BASE_URL,
            headers={"X-Auth-Token": self.api_key},
            timeout=30.0,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # -- internal request with retry + rate limiting -------------------------

    async def _request(self, method: str, path: str, **params) -> dict:
        """Make a rate-limited API request with exponential backoff retry."""
        if self._client is None:
            raise RuntimeError(
                "Client not initialized. Use 'async with FootballDataClient() as client:'"
            )

        # Strip None params
        params = {k: v for k, v in params.items() if v is not None}

        for attempt in range(MAX_RETRIES):
            await self._rate_limiter.acquire()

            response = await self._client.request(method, path, params=params)

            if response.status_code == 200:
                return response.json()

            if response.status_code in (401, 403):
                raise AuthError(response.text)

            if response.status_code == 429:
                if attempt < MAX_RETRIES - 1:
                    wait = 2 ** attempt * 6  # 6s, 12s, 24s
                    await asyncio.sleep(wait)
                    continue
                raise RateLimitError(response.text)

            if response.status_code >= 500:
                if attempt < MAX_RETRIES - 1:
                    wait = 2 ** attempt  # 1s, 2s, 4s
                    await asyncio.sleep(wait)
                    continue
                raise ApiError(response.status_code, response.text)

            # Other client errors — don't retry
            raise ApiError(response.status_code, response.text)

        # Should not reach here, but just in case
        raise ApiError(0, "Max retries exceeded")  # pragma: no cover

    # -- public API methods --------------------------------------------------

    async def get_matches(
        self,
        competition_code: str,
        season: int | None = None,
        status: str | None = None,
    ) -> list[dict]:
        """Get matches for a competition.

        Args:
            competition_code: Football-data.org competition code (e.g. 'PL', 'CL').
            season: Season start year (e.g. 2024 for 2024-25).
            status: Match status filter (SCHEDULED, FINISHED, IN_PLAY, etc.).

        Returns:
            List of match dicts from the API response.
        """
        data = await self._request(
            "GET",
            f"/competitions/{competition_code}/matches",
            season=season,
            status=status,
        )
        return data.get("matches", [])

    async def get_team(self, team_id: int) -> dict:
        """Get team details by ID.

        Args:
            team_id: Football-data.org team ID.

        Returns:
            Team dict from the API response.
        """
        return await self._request("GET", f"/teams/{team_id}")

    async def get_competition_teams(
        self,
        competition_code: str,
        season: int | None = None,
    ) -> list[dict]:
        """Get teams for a competition.

        Args:
            competition_code: Football-data.org competition code.
            season: Season start year (e.g. 2024 for 2024-25).

        Returns:
            List of team dicts from the API response.
        """
        data = await self._request(
            "GET",
            f"/competitions/{competition_code}/teams",
            season=season,
        )
        return data.get("teams", [])
