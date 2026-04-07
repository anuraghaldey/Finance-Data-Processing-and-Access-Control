"""Tests for DSA warm-up and cross-worker sync."""
import json
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


def make_record(amount='100.00', type_='income', category='Salary',
                rdate=None, tags=None, rid='rec-1', description=None):
    """Build a FinancialRecord-like object."""
    return SimpleNamespace(
        id=rid,
        date=rdate or date(2026, 4, 1),
        amount=Decimal(amount),
        type=type_,
        category=category,
        tags=tags or [],
        description=description,
    )


class TestPublishDsaEvent:
    def test_publish_add_event_payload(self):
        """publish_dsa_event sends correctly-shaped payload with PID."""
        from app.utils import dsa_sync

        mock_redis = MagicMock()
        record = make_record(amount='250.50', category='Groceries', tags=['food'])

        with patch.object(dsa_sync, 'get_redis', return_value=mock_redis):
            result = dsa_sync.publish_dsa_event('add', record)

        assert result is True
        mock_redis.publish.assert_called_once()
        channel, raw_payload = mock_redis.publish.call_args[0]
        assert channel == 'dsa:update'
        payload = json.loads(raw_payload)
        assert payload['action'] == 'add'
        assert '_pid' in payload
        assert payload['record']['amount'] == '250.50'
        assert payload['record']['category'] == 'Groceries'
        assert payload['record']['tags'] == ['food']

    def test_publish_returns_false_when_redis_down(self):
        """publish_dsa_event degrades gracefully when Redis is None."""
        from app.utils import dsa_sync
        with patch.object(dsa_sync, 'get_redis', return_value=None):
            assert dsa_sync.publish_dsa_event('add', make_record()) is False

    def test_publish_swallows_redis_errors(self):
        """publish_dsa_event returns False on Redis exceptions, doesn't crash."""
        from app.utils import dsa_sync
        mock_redis = MagicMock()
        mock_redis.publish.side_effect = Exception('connection lost')
        with patch.object(dsa_sync, 'get_redis', return_value=mock_redis):
            assert dsa_sync.publish_dsa_event('add', make_record()) is False


class TestApplyEvent:
    def test_apply_add_updates_local_dsas(self):
        """Remote 'add' event updates local Segment Tree, Trie, TopK."""
        from app.utils import dsa_sync, analytics, search, top_k

        # Reset singletons to fresh state
        analytics._segment_tree = None
        search._search_trie = None
        top_k._dashboard_topk = None

        payload = {
            'action': 'add',
            'record': {
                'id': 'remote-1',
                'date': '2026-04-10',
                'amount': '500.00',
                'type': 'expense',
                'category': 'Travel',
                'tags': ['business'],
            },
        }

        dsa_sync._apply_event(payload, origin_pid=-1)  # -1 != our PID

        # Segment tree got the expense
        tree = analytics.get_segment_tree()
        result = tree.query_range(date(2026, 4, 1), date(2026, 4, 30))
        assert result['expense_sum'] == Decimal('500.00')
        assert result['count'] == 1

        # Trie got the category
        trie = search.get_search_trie()
        hits = trie.search_prefix('Tra', max_results=5)
        assert any(h.get('word') == 'Travel' for h in hits)

        # TopK got the expense category
        topk = top_k.get_dashboard_topk()
        top_cats = topk.get_top_expense_categories()
        assert any(c.get('key') == 'Travel' for c in top_cats)

    def test_apply_event_skips_own_pid(self):
        """Events originating from this worker are NOT re-applied (no double-count)."""
        import os
        from app.utils import dsa_sync, analytics

        analytics._segment_tree = None
        tree_before = analytics.get_segment_tree()
        before = tree_before.query_range(date(2026, 1, 1), date(2026, 12, 31))

        payload = {
            'action': 'add',
            'record': {
                'id': 'x', 'date': '2026-04-10', 'amount': '999.00',
                'type': 'income', 'category': 'X', 'tags': [],
            },
        }
        dsa_sync._apply_event(payload, origin_pid=os.getpid())

        after = analytics.get_segment_tree().query_range(
            date(2026, 1, 1), date(2026, 12, 31)
        )
        assert after['count'] == before['count']
        assert after['income_sum'] == before['income_sum']

    def test_apply_remove_reverses_add(self):
        """'remove' event correctly reverses a prior 'add'."""
        from app.utils import dsa_sync, analytics, top_k

        analytics._segment_tree = None
        top_k._dashboard_topk = None

        rec_payload = {
            'id': 'r1', 'date': '2026-04-15', 'amount': '200.00',
            'type': 'expense', 'category': 'Food', 'tags': [],
        }
        dsa_sync._apply_event({'action': 'add', 'record': rec_payload}, origin_pid=-1)
        dsa_sync._apply_event({'action': 'remove', 'record': rec_payload}, origin_pid=-1)

        tree = analytics.get_segment_tree()
        result = tree.query_range(date(2026, 4, 1), date(2026, 4, 30))
        assert result['expense_sum'] == Decimal('0.00')
        assert result['count'] == 0


class TestWarmUp:
    def test_warm_up_rebuilds_all_three_dsas(self):
        """warm_up_dsas queries records and rebuilds Segment Tree, Trie, TopK."""
        from app.utils import dsa_sync, analytics, search, top_k

        records = [
            make_record(amount='1000', type_='income', category='Salary',
                        rdate=date(2026, 4, 1), tags=['monthly']),
            make_record(amount='50', type_='expense', category='Coffee',
                        rdate=date(2026, 4, 2), tags=[], rid='r2'),
            make_record(amount='200', type_='expense', category='Food',
                        rdate=date(2026, 4, 3), tags=['lunch'], rid='r3'),
        ]

        # Fake Flask app with app_context + logger
        fake_app = MagicMock()
        fake_app.app_context.return_value.__enter__ = MagicMock(return_value=None)
        fake_app.app_context.return_value.__exit__ = MagicMock(return_value=None)

        # Patch the DB query to return our fake records
        mock_query = MagicMock()
        mock_query.filter.return_value.all.return_value = records

        with patch('app.models.financial_record.FinancialRecord') as MockModel:
            MockModel.query = mock_query
            MockModel.deleted_at = MagicMock()
            MockModel.deleted_at.is_.return_value = MagicMock()

            # Reset singletons
            analytics._segment_tree = None
            search._search_trie = None
            top_k._dashboard_topk = None

            dsa_sync.warm_up_dsas(fake_app)

        tree = analytics.get_segment_tree()
        summary = tree.query_range(date(2026, 4, 1), date(2026, 4, 30))
        assert summary['income_sum'] == Decimal('1000')
        assert summary['expense_sum'] == Decimal('250')
        assert summary['count'] == 3

        trie = search.get_search_trie()
        assert len(trie.search_prefix('Sal', max_results=5)) > 0
        assert len(trie.search_prefix('Foo', max_results=5)) > 0

        topk = top_k.get_dashboard_topk()
        top_expenses = topk.get_top_expense_categories()
        assert len(top_expenses) >= 2

    def test_warm_up_handles_empty_db(self):
        """warm_up_dsas with zero records doesn't crash."""
        from app.utils import dsa_sync, analytics
        analytics._segment_tree = None

        fake_app = MagicMock()
        fake_app.app_context.return_value.__enter__ = MagicMock(return_value=None)
        fake_app.app_context.return_value.__exit__ = MagicMock(return_value=None)

        mock_query = MagicMock()
        mock_query.filter.return_value.all.return_value = []

        with patch('app.models.financial_record.FinancialRecord') as MockModel:
            MockModel.query = mock_query
            MockModel.deleted_at.is_.return_value = MagicMock()
            dsa_sync.warm_up_dsas(fake_app)  # should not raise

    def test_warm_up_swallows_db_errors(self):
        """warm_up_dsas logs but doesn't crash if DB query fails."""
        from app.utils import dsa_sync

        fake_app = MagicMock()
        fake_app.app_context.return_value.__enter__ = MagicMock(return_value=None)
        fake_app.app_context.return_value.__exit__ = MagicMock(return_value=None)

        with patch('app.models.financial_record.FinancialRecord') as MockModel:
            MockModel.query.filter.side_effect = Exception('db down')
            MockModel.deleted_at.is_.return_value = MagicMock()
            dsa_sync.warm_up_dsas(fake_app)  # should not raise

        fake_app.logger.warning.assert_called()


class TestEndToEndSyncScenario:
    def test_cross_worker_add_converges(self):
        """Simulates Worker 1 publishing an add event; Worker 2 applies it."""
        from app.utils import dsa_sync, analytics, top_k

        analytics._segment_tree = None
        top_k._dashboard_topk = None

        # --- Worker 1 side: publish ---
        mock_redis = MagicMock()
        record = make_record(amount='750.00', type_='expense',
                             category='Rent', rdate=date(2026, 4, 5))
        with patch.object(dsa_sync, 'get_redis', return_value=mock_redis):
            assert dsa_sync.publish_dsa_event('add', record) is True

        _, published_payload = mock_redis.publish.call_args[0]
        payload = json.loads(published_payload)

        # --- Worker 2 side: apply (pretend we're a different PID) ---
        dsa_sync._apply_event(payload, origin_pid=-999)

        tree = analytics.get_segment_tree()
        result = tree.query_range(date(2026, 4, 1), date(2026, 4, 30))
        assert result['expense_sum'] == Decimal('750.00')
        assert result['count'] == 1

        topk = top_k.get_dashboard_topk()
        top_cats = topk.get_top_expense_categories()
        assert any(c.get('key') == 'Rent' for c in top_cats)
