"""Unit tests for LRU Cache (Doubly Linked List + HashMap)."""

import pytest

from app.utils.cache import LRUCache


@pytest.fixture
def cache():
    return LRUCache(max_capacity=3)


class TestLRUCache:
    def test_put_and_get(self, cache):
        cache.put('a', 1)
        assert cache.get('a') == 1

    def test_miss_returns_none(self, cache):
        assert cache.get('nonexistent') is None

    def test_eviction_on_capacity(self, cache):
        cache.put('a', 1)
        cache.put('b', 2)
        cache.put('c', 3)
        cache.put('d', 4)  # Should evict 'a' (LRU)

        assert cache.get('a') is None
        assert cache.get('b') == 2
        assert cache.get('d') == 4
        assert cache.size == 3

    def test_access_promotes_to_mru(self, cache):
        cache.put('a', 1)
        cache.put('b', 2)
        cache.put('c', 3)

        cache.get('a')  # Promote 'a' to most recent

        cache.put('d', 4)  # Should evict 'b' (now LRU), not 'a'
        assert cache.get('a') == 1
        assert cache.get('b') is None

    def test_update_existing_key(self, cache):
        cache.put('a', 1)
        cache.put('a', 10)
        assert cache.get('a') == 10
        assert cache.size == 1

    def test_invalidate(self, cache):
        cache.put('a', 1)
        cache.put('b', 2)

        cache.invalidate('a')
        assert cache.get('a') is None
        assert cache.size == 1

    def test_invalidate_nonexistent(self, cache):
        cache.invalidate('nonexistent')  # Should not raise
        assert cache.size == 0

    def test_clear(self, cache):
        cache.put('a', 1)
        cache.put('b', 2)
        cache.clear()
        assert cache.size == 0
        assert cache.get('a') is None

    def test_complex_scenario(self, cache):
        """Test a sequence of operations."""
        cache.put('a', 1)
        cache.put('b', 2)
        cache.put('c', 3)

        assert cache.get('a') == 1  # a promoted

        cache.put('d', 4)  # evicts b
        assert cache.get('b') is None

        cache.put('e', 5)  # evicts c
        assert cache.get('c') is None

        assert cache.get('a') == 1
        assert cache.get('d') == 4
        assert cache.get('e') == 5
