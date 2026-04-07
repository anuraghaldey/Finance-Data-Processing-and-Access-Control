"""Segment Tree with Lazy Propagation for date-range financial analytics."""

from datetime import date, timedelta
from decimal import Decimal


class SegmentTreeNode:
    __slots__ = ['total_sum', 'income_sum', 'expense_sum',
                 'max_txn', 'min_txn', 'count', 'lazy_factor']

    def __init__(self):
        self.total_sum = Decimal('0')
        self.income_sum = Decimal('0')
        self.expense_sum = Decimal('0')
        self.max_txn = Decimal('0')
        self.min_txn = Decimal('Infinity')
        self.count = 0
        self.lazy_factor = Decimal('1')  # multiplicative lazy for bulk adjustments


class FinanceSegmentTree:
    """
    Segment tree for financial analytics indexed by date.

    The tree covers a fixed date range [start_date, end_date].
    Each leaf corresponds to one day.
    """

    def __init__(self, start_date=None, end_date=None):
        self.start_date = start_date or date(2020, 1, 1)
        self.end_date = end_date or date(2030, 12, 31)
        self.n = (self.end_date - self.start_date).days + 1
        self.tree = [SegmentTreeNode() for _ in range(4 * self.n)]

    def _date_to_index(self, d):
        delta = (d - self.start_date).days
        return max(0, min(delta, self.n - 1))

    def _merge(self, left, right, target):
        target.total_sum = left.total_sum + right.total_sum
        target.income_sum = left.income_sum + right.income_sum
        target.expense_sum = left.expense_sum + right.expense_sum
        target.max_txn = max(left.max_txn, right.max_txn)
        target.min_txn = min(left.min_txn, right.min_txn)
        target.count = left.count + right.count

    def _push_down(self, node):
        factor = self.tree[node].lazy_factor
        if factor != Decimal('1'):
            for child in [2 * node, 2 * node + 1]:
                if child < len(self.tree):
                    self.tree[child].total_sum *= factor
                    self.tree[child].income_sum *= factor
                    self.tree[child].expense_sum *= factor
                    if self.tree[child].count > 0:
                        self.tree[child].max_txn *= factor
                        self.tree[child].min_txn *= factor
                    self.tree[child].lazy_factor *= factor
            self.tree[node].lazy_factor = Decimal('1')

    def add_record(self, record_date, amount, record_type):
        idx = self._date_to_index(record_date)
        self._update(1, 0, self.n - 1, idx, amount, record_type, is_add=True)

    def remove_record(self, record_date, amount, record_type):
        idx = self._date_to_index(record_date)
        self._update(1, 0, self.n - 1, idx, amount, record_type, is_add=False)

    def _update(self, node, start, end, idx, amount, record_type, is_add):
        if start == end:
            leaf = self.tree[node]
            if is_add:
                leaf.total_sum += amount
                if record_type == 'income':
                    leaf.income_sum += amount
                else:
                    leaf.expense_sum += amount
                leaf.max_txn = max(leaf.max_txn, amount)
                leaf.count += 1
                if leaf.min_txn == Decimal('Infinity') or amount < leaf.min_txn:
                    leaf.min_txn = amount
            else:
                leaf.total_sum -= amount
                if record_type == 'income':
                    leaf.income_sum -= amount
                else:
                    leaf.expense_sum -= amount
                leaf.count = max(0, leaf.count - 1)
                # min/max may be stale after removal; acceptable trade-off
            return

        self._push_down(node)
        mid = (start + end) // 2
        if idx <= mid:
            self._update(2 * node, start, mid, idx, amount, record_type, is_add)
        else:
            self._update(2 * node + 1, mid + 1, end, idx, amount, record_type, is_add)
        self._merge(self.tree[2 * node], self.tree[2 * node + 1], self.tree[node])

    def query_range(self, from_date, to_date):
        """Query aggregated data for a date range."""
        l_idx = self._date_to_index(from_date)
        r_idx = self._date_to_index(to_date)
        result = SegmentTreeNode()
        self._query(1, 0, self.n - 1, l_idx, r_idx, result)
        return {
            'total_sum': result.total_sum,
            'income_sum': result.income_sum,
            'expense_sum': result.expense_sum,
            'max_transaction': result.max_txn if result.count > 0 else Decimal('0'),
            'min_transaction': result.min_txn if result.count > 0 else Decimal('0'),
            'count': result.count,
        }

    def _query(self, node, start, end, l, r, result):
        if r < start or end < l:
            return
        if l <= start and end <= r:
            # Merge this node into result
            combined = SegmentTreeNode()
            combined.total_sum = result.total_sum + self.tree[node].total_sum
            combined.income_sum = result.income_sum + self.tree[node].income_sum
            combined.expense_sum = result.expense_sum + self.tree[node].expense_sum
            combined.max_txn = max(result.max_txn, self.tree[node].max_txn)
            combined.min_txn = min(result.min_txn, self.tree[node].min_txn)
            combined.count = result.count + self.tree[node].count
            result.total_sum = combined.total_sum
            result.income_sum = combined.income_sum
            result.expense_sum = combined.expense_sum
            result.max_txn = combined.max_txn
            result.min_txn = combined.min_txn
            result.count = combined.count
            return

        self._push_down(node)
        mid = (start + end) // 2
        self._query(2 * node, start, mid, l, r, result)
        self._query(2 * node + 1, mid + 1, end, l, r, result)

    def range_update(self, from_date, to_date, factor):
        """Bulk-multiply all values in a date range by factor (e.g. 1.10 for 10% adjustment)."""
        l_idx = self._date_to_index(from_date)
        r_idx = self._date_to_index(to_date)
        self._range_update(1, 0, self.n - 1, l_idx, r_idx, Decimal(str(factor)))

    def _range_update(self, node, start, end, l, r, factor):
        if r < start or end < l:
            return
        if l <= start and end <= r:
            self.tree[node].total_sum *= factor
            self.tree[node].income_sum *= factor
            self.tree[node].expense_sum *= factor
            if self.tree[node].count > 0:
                self.tree[node].max_txn *= factor
                self.tree[node].min_txn *= factor
            self.tree[node].lazy_factor *= factor
            return

        self._push_down(node)
        mid = (start + end) // 2
        self._range_update(2 * node, start, mid, l, r, factor)
        self._range_update(2 * node + 1, mid + 1, end, l, r, factor)
        self._merge(self.tree[2 * node], self.tree[2 * node + 1], self.tree[node])


# Singleton — rebuilt on startup from DB
_segment_tree = None


def get_segment_tree():
    global _segment_tree
    if _segment_tree is None:
        _segment_tree = FinanceSegmentTree()
    return _segment_tree


def rebuild_segment_tree(records):
    """Rebuild segment tree from DB records on startup."""
    global _segment_tree
    _segment_tree = FinanceSegmentTree()
    for r in records:
        _segment_tree.add_record(r.date, Decimal(str(r.amount)), r.type)
    return _segment_tree
