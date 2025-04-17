import logging
import time
from unittest.mock import Mock, patch

import pytest

from src.strava.cache.lru_cache import StravaCache
from src.strava.auth.rate_limiter import RateLimiter
from src.server import get_recent_activities_with_pagination, strava_auth


def test_rate_limiter_limits_and_cleanup():
    limiter = RateLimiter()
    # Fill up to 15-min limit
    for _ in range(limiter.limit_15min):
        limiter.add_request()
    assert not limiter.can_make_request(), "Limiter should block requests after reaching 15-min limit"

    # Simulate old requests (older than 15 minutes)
    old_time = time.time() - 3600
    limiter.requests_15min = [old_time] * limiter.limit_15min
    # Now limiter should allow new requests after cleaning old entries
    assert limiter.can_make_request(), "Limiter should allow requests after old entries expire"


def test_strava_cache_ttl_expiration():
    cache = StravaCache(ttl=1)
    cache.set('key', 'value')
    # Immediate retrieval should hit cache
    assert cache.get('key') == 'value'

    # Force expiration by adjusting timestamp
    cache._cache['key']['timestamp'] -= 2
    assert cache.get('key') is None, "Cache should expire items older than TTL"


def test_get_recent_activities_with_pagination_params(monkeypatch):
    # Prepare strava_auth to return a dummy token
    monkeypatch.setattr(strava_auth, 'get_access_token', lambda: 'test_token')
    # Mock make_request to capture params
    with patch.object(strava_auth, 'make_request') as mock_request:
        mock_resp = Mock()
        mock_resp.json.return_value = [{'id': 'a1'}]
        mock_request.return_value = mock_resp

        # Call with parameters exceeding per_page limit
        result = get_recent_activities_with_pagination(before=100, after=50, page=3, per_page=250)
        assert result == [{'id': 'a1'}]
        # Verify make_request called with capped per_page and correct before/after
        expected_params = {'page': 3, 'per_page': 200, 'before': 100, 'after': 50}
        mock_request.assert_called_with(
            'GET',
            '/athlete/activities',
            headers={'Authorization': 'Bearer test_token'},
            params=expected_params
        )

    # Test default call without before/after
    with patch.object(strava_auth, 'get_access_token', return_value='token2'):
        with patch.object(strava_auth, 'make_request') as mock_request2:
            mock_resp2 = Mock()
            mock_resp2.json.return_value = []
            mock_request2.return_value = mock_resp2
            result2 = get_recent_activities_with_pagination()
            assert result2 == []
            # per_page default is 30
            expected_default = {'page': 1, 'per_page': 30}
            mock_request2.assert_called_once()
            # Extract actual params passed
            args, kwargs = mock_request2.call_args
            assert kwargs.get('params') == expected_default
