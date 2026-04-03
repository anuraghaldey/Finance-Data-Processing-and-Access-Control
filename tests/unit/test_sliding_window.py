"""Unit tests for Sliding Window Counter rate limiter."""

import pytest
import time

from app.middleware.rate_limiter import SlidingWindowCounter


class TestSlidingWindowCounter:
    def test_allows_under_limit(self):
        sw = SlidingWindowCounter()
        allowed, remaining, _ = sw.is_allowed('test_user:endpoint', 10)
        assert allowed is True
        assert remaining == 9

    def test_blocks_over_limit(self):
        sw = SlidingWindowCounter()
        identifier = 'test_block:endpoint'
        for _ in range(5):
            sw.is_allowed(identifier, 5)

        allowed, remaining, _ = sw.is_allowed(identifier, 5)
        assert allowed is False
        assert remaining == 0

    def test_different_identifiers_independent(self):
        sw = SlidingWindowCounter()
        for _ in range(5):
            sw.is_allowed('user_a:endpoint', 5)

        # user_b should still be allowed
        allowed, _, _ = sw.is_allowed('user_b:endpoint', 5)
        assert allowed is True

    def test_remaining_decreases(self):
        sw = SlidingWindowCounter()
        identifier = 'test_remaining:endpoint'

        _, rem1, _ = sw.is_allowed(identifier, 10)
        _, rem2, _ = sw.is_allowed(identifier, 10)
        _, rem3, _ = sw.is_allowed(identifier, 10)

        assert rem1 > rem2 > rem3

    def test_reset_time_returned(self):
        sw = SlidingWindowCounter()
        _, _, reset_at = sw.is_allowed('test_reset:endpoint', 10)
        assert reset_at > int(time.time())
