"""Test suite for the football-data.org API client.

Tests rate limiting, retry/backoff logic, competition mapping, error handling,
and all public API methods using mocked HTTP responses.
"""

import asyncio
import json
import time
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import pytest_asyncio

from src.live.football_data_client import (
    COMPETITION_MAP,
    ApiError,
    AuthError,
    FootballDataClient,
    RateLimitError,
    _RateLimiter,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def client():
    """Create a FootballDataClient with a fake API key."""
    async with FootballDataClient(api_key="test-key-123") as c:
        yield c


# ---------------------------------------------------------------------------
# Competition mapping
# ---------------------------------------------------------------------------
class TestCompetitionMap:
    """Test the COMPETITION_MAP constant."""

    def test_all_domestic_leagues_present(self):
        domestic = [c for c, v in COMPETITION_MAP.items() if v["tier"] == 5]
        assert set(domestic) == {"PL", "PD", "BL1", "SA", "FL1"}

    def test_european_competitions_present(self):
        assert "CL" in COMPETITION_MAP
        assert "EL" in COMPETITION_MAP
        assert "EC" in COMPETITION_MAP

    def test_tier_values(self):
        assert COMPETITION_MAP["CL"]["tier"] == 1
        assert COMPETITION_MAP["EL"]["tier"] == 3
        assert COMPETITION_MAP["EC"]["tier"] == 4

    def test_each_entry_has_required_keys(self):
        for code, info in COMPETITION_MAP.items():
            assert "name" in info, f"{code} missing name"
            assert "country" in info, f"{code} missing country"
            assert "tier" in info, f"{code} missing tier"


# ---------------------------------------------------------------------------
# Auth / initialization
# ---------------------------------------------------------------------------
class TestAuth:
    """Test authentication and initialization."""

    def test_missing_api_key_raises(self):
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(AuthError, match="FOOTBALL_DATA_API_KEY"):
                FootballDataClient(api_key=None)

    def test_env_var_api_key(self):
        with patch.dict("os.environ", {"FOOTBALL_DATA_API_KEY": "env-key"}):
            c = FootballDataClient()
            assert c.api_key == "env-key"

    def test_explicit_api_key_overrides_env(self):
        with patch.dict("os.environ", {"FOOTBALL_DATA_API_KEY": "env-key"}):
            c = FootballDataClient(api_key="explicit-key")
            assert c.api_key == "explicit-key"

    @pytest.mark.asyncio
    async def test_context_manager(self):
        async with FootballDataClient(api_key="test") as c:
            assert c._client is not None
        assert c._client is None

    @pytest.mark.asyncio
    async def test_request_without_context_manager_raises(self):
        c = FootballDataClient(api_key="test")
        with pytest.raises(RuntimeError, match="not initialized"):
            await c._request("GET", "/test")


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------
class TestRateLimiter:
    """Test the token-bucket rate limiter."""

    @pytest.mark.asyncio
    async def test_initial_tokens_available(self):
        rl = _RateLimiter(max_tokens=10, interval=60.0)
        # Starts with 3 tokens (capped initial burst)
        await asyncio.wait_for(rl.acquire(), timeout=1.0)
        assert rl.tokens < 3

    @pytest.mark.asyncio
    async def test_tokens_deplete(self):
        rl = _RateLimiter(max_tokens=3, interval=60.0)
        # Bypass min_delay for unit test
        rl._min_delay = 0
        for _ in range(3):
            await asyncio.wait_for(rl.acquire(), timeout=1.0)
        assert rl.tokens < 1

    @pytest.mark.asyncio
    async def test_tokens_refill_over_time(self):
        rl = _RateLimiter(max_tokens=10, interval=1.0)  # fast refill for testing
        rl._min_delay = 0  # bypass for unit test
        # Drain all tokens
        for _ in range(3):  # only 3 initial tokens
            await rl.acquire()
        # Wait for partial refill
        await asyncio.sleep(0.2)
        rl._refill()
        assert rl.tokens > 0


# ---------------------------------------------------------------------------
# HTTP request mocking helpers
# ---------------------------------------------------------------------------
def _mock_response(status_code: int, json_data: dict | None = None, text: str = ""):
    """Create a mock httpx.Response."""
    if json_data is not None:
        content = json.dumps(json_data).encode()
        headers = {"content-type": "application/json"}
    else:
        content = text.encode()
        headers = {"content-type": "text/plain"}
    return httpx.Response(
        status_code=status_code,
        content=content,
        headers=headers,
        request=httpx.Request("GET", "https://test.example.com"),
    )


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------
class TestErrorHandling:
    """Test HTTP error handling and retries."""

    @pytest.mark.asyncio
    async def test_401_raises_auth_error(self, client):
        mock_resp = _mock_response(401, text="Unauthorized")
        client._client.request = AsyncMock(return_value=mock_resp)
        with pytest.raises(AuthError):
            await client.get_matches("PL")

    @pytest.mark.asyncio
    async def test_403_raises_auth_error(self, client):
        mock_resp = _mock_response(403, text="Forbidden")
        client._client.request = AsyncMock(return_value=mock_resp)
        with pytest.raises(AuthError):
            await client.get_matches("PL")

    @pytest.mark.asyncio
    async def test_404_raises_api_error(self, client):
        mock_resp = _mock_response(404, text="Not Found")
        client._client.request = AsyncMock(return_value=mock_resp)
        with pytest.raises(ApiError) as exc_info:
            await client.get_matches("INVALID")
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_429_retries_then_raises(self, client):
        mock_resp = _mock_response(429, text="Rate limited")
        client._client.request = AsyncMock(return_value=mock_resp)
        # Patch sleep to avoid waiting
        with patch("src.live.football_data_client.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(RateLimitError):
                await client.get_matches("PL")
        # Should have tried MAX_RETRIES times
        assert client._client.request.call_count == 3

    @pytest.mark.asyncio
    async def test_500_retries_then_raises(self, client):
        mock_resp = _mock_response(500, text="Internal Server Error")
        client._client.request = AsyncMock(return_value=mock_resp)
        with patch("src.live.football_data_client.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(ApiError) as exc_info:
                await client.get_matches("PL")
        assert exc_info.value.status_code == 500
        assert client._client.request.call_count == 3

    @pytest.mark.asyncio
    async def test_500_retry_succeeds_on_second_attempt(self, client):
        fail_resp = _mock_response(500, text="Server Error")
        ok_resp = _mock_response(200, json_data={"matches": [{"id": 1}]})
        client._client.request = AsyncMock(side_effect=[fail_resp, ok_resp])
        with patch("src.live.football_data_client.asyncio.sleep", new_callable=AsyncMock):
            result = await client.get_matches("PL")
        assert result == [{"id": 1}]
        assert client._client.request.call_count == 2

    @pytest.mark.asyncio
    async def test_429_retry_succeeds_on_second_attempt(self, client):
        fail_resp = _mock_response(429, text="Rate limited")
        ok_resp = _mock_response(200, json_data={"matches": [{"id": 2}]})
        client._client.request = AsyncMock(side_effect=[fail_resp, ok_resp])
        with patch("src.live.football_data_client.asyncio.sleep", new_callable=AsyncMock):
            result = await client.get_matches("PL")
        assert result == [{"id": 2}]


# ---------------------------------------------------------------------------
# API methods
# ---------------------------------------------------------------------------
class TestGetMatches:
    """Test get_matches method."""

    @pytest.mark.asyncio
    async def test_get_matches_basic(self, client):
        matches = [{"id": 1, "homeTeam": {"name": "Arsenal"}}]
        mock_resp = _mock_response(200, json_data={"matches": matches})
        client._client.request = AsyncMock(return_value=mock_resp)

        result = await client.get_matches("PL")
        assert result == matches

        # Verify correct URL
        call_args = client._client.request.call_args
        assert call_args[0] == ("GET", "/competitions/PL/matches")

    @pytest.mark.asyncio
    async def test_get_matches_with_filters(self, client):
        mock_resp = _mock_response(200, json_data={"matches": []})
        client._client.request = AsyncMock(return_value=mock_resp)

        await client.get_matches("PL", season=2024, status="FINISHED")

        call_args = client._client.request.call_args
        params = call_args[1]["params"]
        assert params["season"] == 2024
        assert params["status"] == "FINISHED"

    @pytest.mark.asyncio
    async def test_get_matches_none_filters_excluded(self, client):
        mock_resp = _mock_response(200, json_data={"matches": []})
        client._client.request = AsyncMock(return_value=mock_resp)

        await client.get_matches("CL", season=None, status=None)

        call_args = client._client.request.call_args
        params = call_args[1]["params"]
        assert "season" not in params
        assert "status" not in params


class TestGetTeam:
    """Test get_team method."""

    @pytest.mark.asyncio
    async def test_get_team(self, client):
        team = {"id": 57, "name": "Arsenal FC", "venue": "Emirates Stadium"}
        mock_resp = _mock_response(200, json_data=team)
        client._client.request = AsyncMock(return_value=mock_resp)

        result = await client.get_team(57)
        assert result == team

        call_args = client._client.request.call_args
        assert call_args[0] == ("GET", "/teams/57")


class TestGetCompetitionTeams:
    """Test get_competition_teams method."""

    @pytest.mark.asyncio
    async def test_get_competition_teams(self, client):
        teams = [{"id": 57, "name": "Arsenal FC"}, {"id": 65, "name": "Manchester City FC"}]
        mock_resp = _mock_response(200, json_data={"teams": teams})
        client._client.request = AsyncMock(return_value=mock_resp)

        result = await client.get_competition_teams("PL")
        assert result == teams

    @pytest.mark.asyncio
    async def test_get_competition_teams_with_season(self, client):
        mock_resp = _mock_response(200, json_data={"teams": []})
        client._client.request = AsyncMock(return_value=mock_resp)

        await client.get_competition_teams("BL1", season=2024)

        call_args = client._client.request.call_args
        assert call_args[1]["params"]["season"] == 2024


# ---------------------------------------------------------------------------
# Exception classes
# ---------------------------------------------------------------------------
class TestExceptions:
    """Test custom exception hierarchy."""

    def test_api_error_attributes(self):
        err = ApiError(404, "Not found")
        assert err.status_code == 404
        assert err.message == "Not found"
        assert "404" in str(err)

    def test_rate_limit_error_is_api_error(self):
        err = RateLimitError()
        assert isinstance(err, ApiError)
        assert err.status_code == 429

    def test_auth_error_is_api_error(self):
        err = AuthError()
        assert isinstance(err, ApiError)
        assert err.status_code == 401
