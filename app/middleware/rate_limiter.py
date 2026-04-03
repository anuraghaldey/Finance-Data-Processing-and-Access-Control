"""
Custom sliding window rate limiter with per-role granularity.

Uses a time-bucketed sliding window algorithm:
- Divides time into fixed-size buckets (e.g., 1-minute intervals)
- Counts requests per bucket
- Slides the window continuously for accurate rate calculation
- Avoids the burst problem at window boundaries that fixed-window counters have

This works alongside Flask-Limiter for basic per-endpoint limits.
"""

import time
from functools import wraps

from flask import jsonify, request
from flask_jwt_extended import get_jwt, verify_jwt_in_request

from app.extensions import get_redis


# Requests per hour by role
ROLE_LIMITS = {
    'viewer': 100,
    'analyst': 300,
    'manager': 500,
    'admin': 1000,
    'super_admin': 2000,
}

WINDOW_SIZE = 3600  # 1 hour in seconds
BUCKET_SIZE = 60    # 1 minute per bucket
NUM_BUCKETS = WINDOW_SIZE // BUCKET_SIZE  # 60 buckets


class SlidingWindowCounter:
    """
    Sliding window rate limiter.

    Instead of a single counter that resets at window boundaries,
    we maintain per-minute bucket counts. The effective count is
    the sum of all buckets within the sliding window.

    This prevents the edge case where a user sends max_requests at
    the end of one window and max_requests at the start of the next,
    effectively doubling their rate.
    """

    def __init__(self):
        self._local_counters = {}  # Fallback when Redis unavailable

    def _get_bucket_key(self, identifier, bucket_time):
        return f'ratelimit:{identifier}:{bucket_time}'

    def _current_bucket(self):
        return int(time.time()) // BUCKET_SIZE * BUCKET_SIZE

    def is_allowed(self, identifier, max_requests):
        """
        Check if a request is allowed under the rate limit.
        Returns (allowed: bool, remaining: int, reset_at: int).
        """
        r = get_redis()
        current = self._current_bucket()
        window_start = current - WINDOW_SIZE + BUCKET_SIZE

        if r:
            return self._check_redis(r, identifier, max_requests, current, window_start)
        return self._check_local(identifier, max_requests, current, window_start)

    def _check_redis(self, r, identifier, max_requests, current, window_start):
        pipe = r.pipeline()

        # Increment current bucket
        key = self._get_bucket_key(identifier, current)
        pipe.incr(key)
        pipe.expire(key, WINDOW_SIZE + BUCKET_SIZE)

        # Get all bucket counts in window
        bucket_keys = [
            self._get_bucket_key(identifier, window_start + i * BUCKET_SIZE)
            for i in range(NUM_BUCKETS)
        ]
        for bk in bucket_keys:
            pipe.get(bk)

        results = pipe.execute()
        # First 2 results are INCR and EXPIRE; rest are GET results
        counts = results[2:]
        total = sum(int(c) for c in counts if c)

        remaining = max(0, max_requests - total)
        reset_at = current + BUCKET_SIZE

        return total <= max_requests, remaining, reset_at

    def _check_local(self, identifier, max_requests, current, window_start):
        """In-memory fallback when Redis is unavailable."""
        # Increment current bucket
        key = (identifier, current)
        self._local_counters[key] = self._local_counters.get(key, 0) + 1

        # Sum all buckets in window
        total = 0
        for i in range(NUM_BUCKETS):
            bucket_time = window_start + i * BUCKET_SIZE
            total += self._local_counters.get((identifier, bucket_time), 0)

        # Cleanup old buckets
        cutoff = window_start - BUCKET_SIZE
        self._local_counters = {
            k: v for k, v in self._local_counters.items()
            if k[1] >= cutoff
        }

        remaining = max(0, max_requests - total)
        reset_at = current + BUCKET_SIZE

        return total <= max_requests, remaining, reset_at


# Singleton instance
sliding_window = SlidingWindowCounter()


def role_rate_limit(fn):
    """
    Decorator that applies per-role rate limiting using sliding window.
    Reads the role from JWT claims and applies the corresponding limit.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request()
            claims = get_jwt()
            role_name = claims.get('role', 'viewer')
            user_id = claims.get('sub', request.remote_addr)
        except Exception:
            role_name = 'viewer'
            user_id = request.remote_addr

        max_requests = ROLE_LIMITS.get(role_name, 100)
        identifier = f'{user_id}:{request.endpoint}'

        allowed, remaining, reset_at = sliding_window.is_allowed(identifier, max_requests)

        if not allowed:
            response = jsonify({
                'error': 'Rate limit exceeded',
                'retry_after': reset_at - int(time.time()),
            })
            response.status_code = 429
            response.headers['X-RateLimit-Limit'] = str(max_requests)
            response.headers['X-RateLimit-Remaining'] = '0'
            response.headers['X-RateLimit-Reset'] = str(reset_at)
            response.headers['Retry-After'] = str(reset_at - int(time.time()))
            return response

        # Attach rate limit headers to the response
        result = fn(*args, **kwargs)

        # Handle both tuple and Response returns
        if isinstance(result, tuple):
            response = result[0] if hasattr(result[0], 'headers') else jsonify(result[0])
            status = result[1] if len(result) > 1 else 200
        else:
            response = result
            status = None

        if hasattr(response, 'headers'):
            response.headers['X-RateLimit-Limit'] = str(max_requests)
            response.headers['X-RateLimit-Remaining'] = str(remaining)
            response.headers['X-RateLimit-Reset'] = str(reset_at)

        if status:
            return response, status
        return response

    return wrapper
