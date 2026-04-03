"""Unit tests for Min-Heap Top-K tracker."""

import pytest
from decimal import Decimal

from app.utils.top_k import TopKTracker, DashboardTopK


class TestTopKTracker:
    def test_basic_insert(self):
        tk = TopKTracker(k=3)
        tk.update('a', 100)
        tk.update('b', 200)
        tk.update('c', 300)

        top = tk.get_top_k()
        assert len(top) == 3
        assert top[0]['key'] == 'c'
        assert top[0]['value'] == Decimal('300')

    def test_eviction_of_smallest(self):
        tk = TopKTracker(k=2)
        tk.update('a', 100)
        tk.update('b', 200)
        tk.update('c', 300)  # Evicts 'a'

        top = tk.get_top_k()
        keys = [item['key'] for item in top]
        assert 'a' not in keys
        assert 'b' in keys
        assert 'c' in keys

    def test_update_existing_key(self):
        tk = TopKTracker(k=3)
        tk.update('a', 100)
        tk.update('b', 200)
        tk.update('a', 500)  # Update 'a'

        top = tk.get_top_k()
        assert top[0]['key'] == 'a'
        assert top[0]['value'] == Decimal('500')

    def test_peek_min(self):
        tk = TopKTracker(k=3)
        tk.update('a', 100)
        tk.update('b', 200)
        tk.update('c', 300)

        assert tk.peek_min()['key'] == 'a'

    def test_empty_tracker(self):
        tk = TopKTracker(k=3)
        assert tk.get_top_k() == []
        assert tk.peek_min() is None

    def test_sorted_descending(self):
        tk = TopKTracker(k=5)
        for i, val in enumerate([50, 10, 90, 30, 70]):
            tk.update(f'item_{i}', val)

        top = tk.get_top_k()
        values = [item['value'] for item in top]
        assert values == sorted(values, reverse=True)


class TestDashboardTopK:
    def test_category_tracking(self):
        dtk = DashboardTopK(k=3)
        dtk.add_record('expense', 'Food', 100)
        dtk.add_record('expense', 'Food', 200)
        dtk.add_record('expense', 'Rent', 1000)
        dtk.add_record('income', 'Salary', 5000)

        top_exp = dtk.get_top_expense_categories()
        assert top_exp[0]['key'] == 'Rent'

        top_inc = dtk.get_top_income_categories()
        assert top_inc[0]['key'] == 'Salary'

    def test_remove_adjusts_totals(self):
        dtk = DashboardTopK(k=3)
        dtk.add_record('expense', 'Food', 500)
        dtk.remove_record('expense', 'Food', 300)

        top = dtk.get_top_expense_categories()
        assert top[0]['value'] == Decimal('200')
