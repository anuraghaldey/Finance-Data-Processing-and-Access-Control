"""
Dashboard service — aggregated analytics endpoints.

Layered caching strategy:
  1. L1: LRU Cache (in-process, ~50ns)
  2. L2: Redis (shared, ~0.5ms)
  3. In-memory DSA (Segment Tree, Min-Heap)
  4. PostgreSQL (fallback, full query)
"""

import json
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func

from app.extensions import db, get_redis
from app.models.financial_record import FinancialRecord
from app.utils.cache import dashboard_cache
from app.utils.analytics import get_segment_tree
from app.utils.top_k import get_dashboard_topk


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, date):
            return obj.isoformat()
        return super().default(obj)


def _cache_get(key):
    """Try L1 then L2 cache."""
    # L1
    result = dashboard_cache.get(key)
    if result is not None:
        return result

    # L2
    r = get_redis()
    if r:
        try:
            data = r.get(f'dashboard:{key}')
            if data:
                parsed = json.loads(data)
                dashboard_cache.put(key, parsed)  # Promote to L1
                return parsed
        except Exception:
            pass

    return None


def _cache_set(key, value, ttl=300):
    """Set in both L1 and L2."""
    dashboard_cache.put(key, value)

    r = get_redis()
    if r:
        try:
            r.setex(f'dashboard:{key}', ttl, json.dumps(value, cls=DecimalEncoder))
        except Exception:
            pass


def get_summary(date_from=None, date_to=None):
    """
    Dashboard summary: total income, expenses, net balance, count, average.
    Uses Segment Tree for O(log n) range queries.
    """
    if date_from is None:
        date_from = date(2020, 1, 1)
    if date_to is None:
        date_to = date.today()

    cache_key = f'summary:{date_from}:{date_to}'
    cached = _cache_get(cache_key)
    if cached:
        return cached

    # Try Segment Tree first
    tree = get_segment_tree()
    data = tree.query_range(date_from, date_to)

    if data['count'] > 0:
        result = {
            'total_income': str(data['income_sum']),
            'total_expenses': str(data['expense_sum']),
            'net_balance': str(data['income_sum'] - data['expense_sum']),
            'record_count': data['count'],
            'avg_transaction': str(
                (data['total_sum'] / data['count']).quantize(Decimal('0.01'))
            ) if data['count'] > 0 else '0.00',
            'max_transaction': str(data['max_transaction']),
            'min_transaction': str(data['min_transaction']),
            'period': {'from': str(date_from), 'to': str(date_to)},
        }
    else:
        # Fallback to PostgreSQL
        result = _summary_from_db(date_from, date_to)

    _cache_set(cache_key, result)
    return result


def _summary_from_db(date_from, date_to):
    """Fallback: compute summary directly from PostgreSQL."""
    base = FinancialRecord.query.filter(
        FinancialRecord.deleted_at.is_(None),
        FinancialRecord.date.between(date_from, date_to),
    )

    income = base.filter_by(type='income').with_entities(
        func.coalesce(func.sum(FinancialRecord.amount), 0)
    ).scalar()

    expense = base.filter_by(type='expense').with_entities(
        func.coalesce(func.sum(FinancialRecord.amount), 0)
    ).scalar()

    count = base.count()
    total = income + expense

    return {
        'total_income': str(income),
        'total_expenses': str(expense),
        'net_balance': str(income - expense),
        'record_count': count,
        'avg_transaction': str(
            (Decimal(str(total)) / count).quantize(Decimal('0.01'))
        ) if count > 0 else '0.00',
        'max_transaction': str(
            base.with_entities(func.coalesce(func.max(FinancialRecord.amount), 0)).scalar()
        ),
        'min_transaction': str(
            base.with_entities(func.coalesce(func.min(FinancialRecord.amount), 0)).scalar()
        ),
        'period': {'from': str(date_from), 'to': str(date_to)},
    }


def get_category_breakdown(date_from=None, date_to=None):
    """Category-wise totals with top categories from Min-Heap."""
    if date_from is None:
        date_from = date(2020, 1, 1)
    if date_to is None:
        date_to = date.today()

    cache_key = f'categories:{date_from}:{date_to}'
    cached = _cache_get(cache_key)
    if cached:
        return cached

    # Full breakdown from DB (needed for percentages)
    rows = db.session.query(
        FinancialRecord.category,
        FinancialRecord.type,
        func.sum(FinancialRecord.amount).label('total'),
        func.count(FinancialRecord.id).label('count'),
    ).filter(
        FinancialRecord.deleted_at.is_(None),
        FinancialRecord.date.between(date_from, date_to),
    ).group_by(
        FinancialRecord.category, FinancialRecord.type
    ).all()

    grand_total = sum(r.total for r in rows) if rows else Decimal('0')

    categories = []
    for row in rows:
        pct = (row.total / grand_total * 100).quantize(Decimal('0.1')) if grand_total > 0 else Decimal('0')
        categories.append({
            'name': row.category,
            'type': row.type,
            'total': str(row.total),
            'percentage': str(pct),
            'count': row.count,
        })

    # Top categories from Min-Heap (O(1))
    topk = get_dashboard_topk()
    result = {
        'categories': categories,
        'top_expense_categories': topk.get_top_expense_categories(),
        'top_income_categories': topk.get_top_income_categories(),
        'period': {'from': str(date_from), 'to': str(date_to)},
    }

    _cache_set(cache_key, result)
    return result


def get_trends(period='monthly', months=6):
    """Monthly or weekly trends."""
    cache_key = f'trends:{period}:{months}'
    cached = _cache_get(cache_key)
    if cached:
        return cached

    today = date.today()

    if period == 'monthly':
        trends = _monthly_trends(today, months)
    else:
        trends = _weekly_trends(today, months * 4)

    result = {
        'period': period,
        'trends': trends,
    }

    _cache_set(cache_key, result)
    return result


def _monthly_trends(today, months):
    """Compute monthly trends using Segment Tree for each month."""
    tree = get_segment_tree()
    trends = []

    for i in range(months - 1, -1, -1):
        year = today.year
        month = today.month - i
        while month <= 0:
            month += 12
            year -= 1

        month_start = date(year, month, 1)
        if month == 12:
            month_end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(year, month + 1, 1) - timedelta(days=1)

        data = tree.query_range(month_start, month_end)

        trends.append({
            'period': f'{year}-{month:02d}',
            'income': str(data['income_sum']),
            'expense': str(data['expense_sum']),
            'net': str(data['income_sum'] - data['expense_sum']),
            'count': data['count'],
        })

    return trends


def _weekly_trends(today, weeks):
    """Compute weekly trends using Segment Tree."""
    tree = get_segment_tree()
    trends = []

    for i in range(weeks - 1, -1, -1):
        week_end = today - timedelta(weeks=i)
        week_start = week_end - timedelta(days=6)

        data = tree.query_range(week_start, week_end)

        trends.append({
            'period': f'{week_start} to {week_end}',
            'income': str(data['income_sum']),
            'expense': str(data['expense_sum']),
            'net': str(data['income_sum'] - data['expense_sum']),
            'count': data['count'],
        })

    return trends


def get_recent_activity(limit=10):
    """Recent financial records."""
    cache_key = f'recent:{limit}'
    cached = _cache_get(cache_key)
    if cached:
        return cached

    records = FinancialRecord.query.filter(
        FinancialRecord.deleted_at.is_(None)
    ).order_by(
        FinancialRecord.created_at.desc()
    ).limit(limit).all()

    result = [{
        'id': str(r.id),
        'type': r.type,
        'amount': str(r.amount),
        'category': r.category,
        'date': str(r.date),
        'description': r.description,
        'created_at': r.created_at.isoformat() if r.created_at else None,
    } for r in records]

    _cache_set(cache_key, result, ttl=60)  # Shorter TTL for recent activity
    return result
