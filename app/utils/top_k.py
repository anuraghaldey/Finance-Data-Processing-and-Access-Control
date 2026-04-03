"""
Min-Heap for Top-K dashboard queries.

Maintains a min-heap of size K for each query type:
  - Top expense categories
  - Top income categories
  - Largest transactions

When a new record is added:
  - Update the relevant heap in O(log K)
  - Dashboard reads top-K in O(1) from heap

DB alternative (GROUP BY + ORDER BY DESC LIMIT K) recomputes the full
aggregation on every request. The heap provides incremental updates.

Memory: ~5 heaps x K entries = ~50 entries total. Negligible (~2 KB).
"""

import heapq
from decimal import Decimal
from collections import defaultdict


class TopKTracker:
    """
    Maintains top-K items using a min-heap.

    The min-heap keeps the K largest items. The smallest item in the heap
    is at the root — if a new item is larger than the root, it replaces it.
    Reading the top-K is O(K log K) for sorted output, O(1) for unsorted.
    """

    def __init__(self, k=10):
        self.k = k
        self.heap = []  # min-heap of (value, key)

    def update(self, key, value):
        """
        Add or update an item. O(log K).
        If heap size < K: push directly.
        If new value > heap min: replace min.
        """
        value = Decimal(str(value))

        # Remove existing entry with same key if present
        self.heap = [(v, k) for v, k in self.heap if k != key]
        heapq.heapify(self.heap)

        if len(self.heap) < self.k:
            heapq.heappush(self.heap, (value, key))
        elif value > self.heap[0][0]:
            heapq.heapreplace(self.heap, (value, key))

    def get_top_k(self):
        """Return top-K items sorted descending. O(K log K)."""
        return [
            {'key': key, 'value': value}
            for value, key in sorted(self.heap, reverse=True)
        ]

    def peek_min(self):
        """Return the smallest item in the top-K. O(1)."""
        if self.heap:
            value, key = self.heap[0]
            return {'key': key, 'value': value}
        return None

    @property
    def size(self):
        return len(self.heap)


class DashboardTopK:
    """Manages multiple top-K trackers for different dashboard queries."""

    def __init__(self, k=10):
        self.k = k
        self.top_expense_categories = TopKTracker(k)
        self.top_income_categories = TopKTracker(k)
        self.largest_transactions = TopKTracker(k)

        # Running category totals for incremental heap updates
        self._category_totals = defaultdict(lambda: {'income': Decimal('0'), 'expense': Decimal('0')})

    def add_record(self, record_type, category, amount):
        """Update heaps when a record is added. O(log K)."""
        amount = Decimal(str(amount))
        self._category_totals[category][record_type] += amount

        if record_type == 'expense':
            self.top_expense_categories.update(
                category, self._category_totals[category]['expense']
            )
        else:
            self.top_income_categories.update(
                category, self._category_totals[category]['income']
            )

        self.largest_transactions.update(
            f'{record_type}:{category}:{amount}', amount
        )

    def remove_record(self, record_type, category, amount):
        """Update heaps when a record is removed. O(K) rebuild."""
        amount = Decimal(str(amount))
        self._category_totals[category][record_type] -= amount

        if record_type == 'expense':
            self.top_expense_categories.update(
                category, self._category_totals[category]['expense']
            )
        else:
            self.top_income_categories.update(
                category, self._category_totals[category]['income']
            )

    def get_top_expense_categories(self):
        return self.top_expense_categories.get_top_k()

    def get_top_income_categories(self):
        return self.top_income_categories.get_top_k()

    def get_largest_transactions(self):
        return self.largest_transactions.get_top_k()


# Singleton
_dashboard_topk = None


def get_dashboard_topk():
    global _dashboard_topk
    if _dashboard_topk is None:
        _dashboard_topk = DashboardTopK()
    return _dashboard_topk


def rebuild_dashboard_topk(records):
    """Rebuild top-K trackers from DB records on startup."""
    global _dashboard_topk
    _dashboard_topk = DashboardTopK()
    for r in records:
        _dashboard_topk.add_record(r.type, r.category, r.amount)
    return _dashboard_topk
