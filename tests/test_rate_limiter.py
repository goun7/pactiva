"""
Pactiva Kayan Zaman Pencereli Hız Sınırlayıcı Testleri (tests/test_rate_limiter.py)
"""

import time
import pytest
from pactiva_core.rate_limiter import SlidingWindowRateLimiter


def test_rate_limiter_allows_under_limit():
    limiter = SlidingWindowRateLimiter()
    key = "client_test_ip_1"

    for i in range(5):
        allowed, remaining, retry_after = limiter.is_allowed(key, max_requests=5, window_seconds=10.0)
        assert allowed is True
        assert remaining == 5 - (i + 1)
        assert retry_after == 0.0


def test_rate_limiter_blocks_over_limit():
    limiter = SlidingWindowRateLimiter()
    key = "client_test_ip_2"

    # İlk 3 istek geçer
    for _ in range(3):
        allowed, _, _ = limiter.is_allowed(key, max_requests=3, window_seconds=5.0)
        assert allowed is True

    # 4. istek kotayı aştığı için reddedilmeli
    allowed, remaining, retry_after = limiter.is_allowed(key, max_requests=3, window_seconds=5.0)
    assert allowed is False
    assert remaining == 0
    assert retry_after > 0.0


def test_rate_limiter_reset():
    limiter = SlidingWindowRateLimiter()
    key = "client_test_ip_3"
    limiter.is_allowed(key, max_requests=1, window_seconds=10.0)
    allowed, _, _ = limiter.is_allowed(key, max_requests=1, window_seconds=10.0)
    assert allowed is False

    limiter.reset()
    allowed_after_reset, _, _ = limiter.is_allowed(key, max_requests=1, window_seconds=10.0)
    assert allowed_after_reset is True
