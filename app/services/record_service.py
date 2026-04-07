from datetime import datetime, timezone
from decimal import Decimal

from app.extensions import db
from app.models.financial_record import FinancialRecord
from app.middleware.audit import log_audit
from app.errors.exceptions import NotFoundException
from app.utils.pagination import paginate_query
from app.utils.analytics import get_segment_tree
from app.utils.search import get_search_trie, tokenize_description
from app.utils.top_k import get_dashboard_topk
from app.utils.dsa_sync import publish_dsa_event


def _update_dsa_on_add(record):
    tree = get_segment_tree()
    tree.add_record(record.date, Decimal(str(record.amount)), record.type)

    trie = get_search_trie()
    trie.insert(record.category, source='category')
    if record.tags:
        for tag in record.tags:
            trie.insert(tag, source='tag')

    topk = get_dashboard_topk()
    topk.add_record(record.type, record.category, record.amount)

    publish_dsa_event('add', record)


def _update_dsa_on_remove(record):
    tree = get_segment_tree()
    tree.remove_record(record.date, Decimal(str(record.amount)), record.type)

    topk = get_dashboard_topk()
    topk.remove_record(record.type, record.category, record.amount)

    publish_dsa_event('remove', record)


def _invalidate_caches():
    from app.utils.cache import dashboard_cache
    dashboard_cache.clear()

    from app.extensions import get_redis
    r = get_redis()
    if r:
        try:
            keys = r.keys('dashboard:*')
            if keys:
                r.delete(*keys)
        except Exception:
            pass


def create_record(data, user_id):
    record = FinancialRecord(
        user_id=user_id,
        amount=Decimal(data['amount']),
        type=data['type'],
        category=data['category'],
        date=data['date'],
        description=data.get('description'),
        tags=data.get('tags', []),
        is_recurring=data.get('is_recurring', False),
    )
    db.session.add(record)

    log_audit('create', 'record', resource_id=record.id,
              new_value={
                  'amount': str(record.amount), 'type': record.type,
                  'category': record.category, 'date': str(record.date),
              })
    db.session.commit()

    _update_dsa_on_add(record)
    _invalidate_caches()

    return record


def get_records(filters):
    query = FinancialRecord.query.filter(FinancialRecord.deleted_at.is_(None))

    if filters.get('type'):
        query = query.filter(FinancialRecord.type == filters['type'])
    if filters.get('category'):
        query = query.filter(FinancialRecord.category.ilike(f"%{filters['category']}%"))
    if filters.get('date_from'):
        query = query.filter(FinancialRecord.date >= filters['date_from'])
    if filters.get('date_to'):
        query = query.filter(FinancialRecord.date <= filters['date_to'])
    if filters.get('min_amount'):
        query = query.filter(FinancialRecord.amount >= Decimal(filters['min_amount']))
    if filters.get('max_amount'):
        query = query.filter(FinancialRecord.amount <= Decimal(filters['max_amount']))
    if filters.get('is_recurring') is not None:
        query = query.filter(FinancialRecord.is_recurring == filters['is_recurring'])

    sort_by = filters.get('sort_by', 'date')
    sort_order = filters.get('sort_order', 'desc')
    cursor = filters.get('cursor')
    limit = filters.get('limit', 20)

    items, next_cursor, has_more = paginate_query(
        query, FinancialRecord, sort_by=sort_by, sort_order=sort_order,
        cursor=cursor, limit=limit,
    )
    return items, next_cursor, has_more


def get_record_by_id(record_id):
    record = FinancialRecord.query.get(record_id)
    if not record or record.is_deleted:
        raise NotFoundException('Financial record')
    return record


def update_record(record_id, data):
    record = get_record_by_id(record_id)

    old_data = {
        'amount': str(record.amount), 'type': record.type,
        'category': record.category, 'date': str(record.date),
    }

    _update_dsa_on_remove(record)

    for field in ['amount', 'type', 'category', 'date', 'description', 'tags', 'is_recurring']:
        if field in data and data[field] is not None:
            if field == 'amount':
                setattr(record, field, Decimal(data[field]))
            else:
                setattr(record, field, data[field])

    log_audit('update', 'record', resource_id=record.id,
              old_value=old_data,
              new_value={
                  'amount': str(record.amount), 'type': record.type,
                  'category': record.category, 'date': str(record.date),
              })
    db.session.commit()

    _update_dsa_on_add(record)
    _invalidate_caches()

    return record


def soft_delete_record(record_id):
    record = get_record_by_id(record_id)

    _update_dsa_on_remove(record)

    record.deleted_at = datetime.now(timezone.utc)

    log_audit('soft_delete', 'record', resource_id=record.id,
              old_value={'amount': str(record.amount), 'type': record.type,
                         'category': record.category})
    db.session.commit()

    _invalidate_caches()
    return record


def hard_delete_record(record_id):
    record = FinancialRecord.query.get(record_id)
    if not record:
        raise NotFoundException('Financial record')

    if not record.is_deleted:
        _update_dsa_on_remove(record)

    log_audit('hard_delete', 'record', resource_id=record.id,
              old_value={'amount': str(record.amount), 'type': record.type,
                         'category': record.category})

    db.session.delete(record)
    db.session.commit()

    _invalidate_caches()
    return True


def search_records(query_text, limit=10):
    trie = get_search_trie()
    suggestions = trie.search_prefix(query_text, max_results=limit)
    return suggestions
