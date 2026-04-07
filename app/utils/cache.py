"""LRU Cache — L1 in-process cache sitting in front of Redis (L2)."""


class _DLLNode:
    """Doubly linked list node."""
    __slots__ = ['key', 'value', 'prev', 'next']

    def __init__(self, key=None, value=None):
        self.key = key
        self.value = value
        self.prev = None
        self.next = None


class LRUCache:
    """Least Recently Used cache using a doubly linked list + hashmap."""

    def __init__(self, max_capacity=128):
        self.capacity = max_capacity
        self.cache = {}  # key -> DLLNode

        # Sentinel nodes (avoid null checks)
        self.head = _DLLNode()  # Most recently used
        self.tail = _DLLNode()  # Least recently used
        self.head.next = self.tail
        self.tail.prev = self.head

    def get(self, key):
        """Retrieve value and promote to most-recently-used."""
        if key not in self.cache:
            return None

        node = self.cache[key]
        self._move_to_front(node)
        return node.value

    def put(self, key, value):
        """Insert or update a key-value pair."""
        if key in self.cache:
            node = self.cache[key]
            node.value = value
            self._move_to_front(node)
            return

        # Evict LRU if at capacity
        if len(self.cache) >= self.capacity:
            self._evict()

        node = _DLLNode(key, value)
        self.cache[key] = node
        self._add_to_front(node)

    def invalidate(self, key):
        """Remove a specific key."""
        if key not in self.cache:
            return
        node = self.cache.pop(key)
        self._remove(node)

    def clear(self):
        """Remove all entries."""
        self.cache.clear()
        self.head.next = self.tail
        self.tail.prev = self.head

    @property
    def size(self):
        return len(self.cache)

    def _add_to_front(self, node):
        """Add node right after head (most recent position)."""
        node.prev = self.head
        node.next = self.head.next
        self.head.next.prev = node
        self.head.next = node

    def _remove(self, node):
        """Remove a node from the linked list."""
        node.prev.next = node.next
        node.next.prev = node.prev

    def _move_to_front(self, node):
        """Move existing node to front (most recent)."""
        self._remove(node)
        self._add_to_front(node)

    def _evict(self):
        """Remove the least recently used node (before tail)."""
        lru = self.tail.prev
        if lru == self.head:
            return  # Empty
        self._remove(lru)
        del self.cache[lru.key]


dashboard_cache = LRUCache(max_capacity=128)
