"""Unit tests for Segment Tree with Lazy Propagation."""

import pytest
from datetime import date
from decimal import Decimal

from app.utils.analytics import FinanceSegmentTree


@pytest.fixture
def tree():
    return FinanceSegmentTree(start_date=date(2026, 1, 1), end_date=date(2026, 12, 31))


class TestSegmentTree:
    def test_empty_query(self, tree):
        result = tree.query_range(date(2026, 1, 1), date(2026, 12, 31))
        assert result['total_sum'] == Decimal('0')
        assert result['count'] == 0

    def test_single_add(self, tree):
        tree.add_record(date(2026, 3, 15), Decimal('1000'), 'income')
        result = tree.query_range(date(2026, 3, 1), date(2026, 3, 31))
        assert result['income_sum'] == Decimal('1000')
        assert result['expense_sum'] == Decimal('0')
        assert result['count'] == 1

    def test_multiple_adds(self, tree):
        tree.add_record(date(2026, 3, 15), Decimal('1000'), 'income')
        tree.add_record(date(2026, 3, 20), Decimal('500'), 'expense')
        tree.add_record(date(2026, 4, 1), Decimal('2000'), 'income')

        # March only
        result = tree.query_range(date(2026, 3, 1), date(2026, 3, 31))
        assert result['income_sum'] == Decimal('1000')
        assert result['expense_sum'] == Decimal('500')
        assert result['count'] == 2

        # Full range
        result = tree.query_range(date(2026, 3, 1), date(2026, 4, 30))
        assert result['income_sum'] == Decimal('3000')
        assert result['count'] == 3

    def test_remove_record(self, tree):
        tree.add_record(date(2026, 5, 10), Decimal('750'), 'expense')
        tree.remove_record(date(2026, 5, 10), Decimal('750'), 'expense')
        result = tree.query_range(date(2026, 5, 1), date(2026, 5, 31))
        assert result['expense_sum'] == Decimal('0')
        assert result['count'] == 0

    def test_range_update_lazy(self, tree):
        tree.add_record(date(2026, 1, 15), Decimal('1000'), 'income')
        tree.add_record(date(2026, 2, 15), Decimal('2000'), 'income')

        # Apply 10% increase to January
        tree.range_update(date(2026, 1, 1), date(2026, 1, 31), Decimal('1.10'))

        jan = tree.query_range(date(2026, 1, 1), date(2026, 1, 31))
        assert jan['income_sum'] == Decimal('1100')

        # February unchanged
        feb = tree.query_range(date(2026, 2, 1), date(2026, 2, 28))
        assert feb['income_sum'] == Decimal('2000')

    def test_max_min_tracking(self, tree):
        tree.add_record(date(2026, 6, 1), Decimal('100'), 'expense')
        tree.add_record(date(2026, 6, 15), Decimal('5000'), 'income')
        tree.add_record(date(2026, 6, 20), Decimal('250'), 'expense')

        result = tree.query_range(date(2026, 6, 1), date(2026, 6, 30))
        assert result['max_transaction'] == Decimal('5000')
        assert result['min_transaction'] == Decimal('100')

    def test_net_balance(self, tree):
        tree.add_record(date(2026, 7, 1), Decimal('5000'), 'income')
        tree.add_record(date(2026, 7, 15), Decimal('3000'), 'expense')

        result = tree.query_range(date(2026, 7, 1), date(2026, 7, 31))
        net = result['income_sum'] - result['expense_sum']
        assert net == Decimal('2000')
