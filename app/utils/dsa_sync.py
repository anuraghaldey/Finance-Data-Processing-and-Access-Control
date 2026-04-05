"""
DSA lifecycle: warm-up on startup + cross-worker sync via Redis Pub/Sub.

- `warm_up_dsas()`: query DB and rebuild Segment Tree, Trie, Top-K for this worker.
- `publish_dsa_event()`: broadcast a write event to all workers via Redis.
- `start_subscriber()`: background thread that applies events from other workers
  to this worker's local DSA structures.

Consistency model: DB is the source of truth. In-memory DSAs are eventually
consistent across workers (~1ms propagation via Pub/Sub). If Redis is down,
workers fall back to periodic DB resync.
"""
import json
import threading
import time
from decimal import Decimal

from app.extensions import get_redis

DSA_CHANNEL = 'dsa:update'
PERIODIC_RESYNC_SECONDS = 30

_subscriber_thread = None
_resync_thread = None
_stop_event = threading.Event()


def warm_up_dsas(app):
    """Rebuild all in-memory DSA structures from PostgreSQL.

    Called on worker startup (post_fork) and as the fallback path when
    Pub/Sub sync fails. Ensures no cold-start serves empty analytics.
    """
    from app.models.financial_record import FinancialRecord
    from app.utils.analytics import rebuild_segment_tree
    from app.utils.search import rebuild_search_trie
    from app.utils.top_k import rebuild_dashboard_topk

    with app.app_context():
        try:
            records = FinancialRecord.query.filter(
                FinancialRecord.deleted_at.is_(None)
            ).all()
            rebuild_segment_tree(records)
            rebuild_search_trie(records)
            rebuild_dashboard_topk(records)
            app.logger.info(f'DSA warm-up complete: {len(records)} records loaded')
        except Exception as e:
            app.logger.warning(f'DSA warm-up failed: {e}')


def publish_dsa_event(action, record):
    """Publish a DSA update event for other workers to consume.

    action: 'add' | 'remove'
    record: FinancialRecord instance (fields extracted before send)
    """
    r = get_redis()
    if not r:
        return False
    try:
        import os
        payload = {
            'action': action,
            '_pid': os.getpid(),
            'record': {
                'id': str(record.id),
                'date': record.date.isoformat(),
                'amount': str(record.amount),
                'type': record.type,
                'category': record.category,
                'tags': list(record.tags) if record.tags else [],
            },
        }
        r.publish(DSA_CHANNEL, json.dumps(payload))
        return True
    except Exception:
        return False


def _apply_event(payload, origin_pid):
    """Apply a remote DSA event to this worker's local structures."""
    import os
    # Skip events originating from this worker (we already applied locally)
    if origin_pid == os.getpid():
        return

    from datetime import date as date_cls
    from app.utils.analytics import get_segment_tree
    from app.utils.search import get_search_trie
    from app.utils.top_k import get_dashboard_topk

    action = payload['action']
    rec = payload['record']
    rec_date = date_cls.fromisoformat(rec['date'])
    amount = Decimal(rec['amount'])

    if action == 'add':
        get_segment_tree().add_record(rec_date, amount, rec['type'])
        trie = get_search_trie()
        trie.insert(rec['category'], source='category')
        for tag in rec.get('tags') or []:
            trie.insert(tag, source='tag')
        get_dashboard_topk().add_record(rec['type'], rec['category'], amount)
    elif action == 'remove':
        get_segment_tree().remove_record(rec_date, amount, rec['type'])
        get_dashboard_topk().remove_record(rec['type'], rec['category'], amount)

    # DSA updated — now drop this worker's L1 dashboard cache so the next
    # read recomputes from the fresh tree instead of serving stale entries.
    from app.utils.cache import dashboard_cache
    dashboard_cache.clear()


def _subscriber_loop(app):
    """Background thread: listens on Redis Pub/Sub and applies events."""
    import os
    my_pid = os.getpid()

    while not _stop_event.is_set():
        r = get_redis()
        if not r:
            time.sleep(5)
            continue
        try:
            pubsub = r.pubsub(ignore_subscribe_messages=True)
            pubsub.subscribe(DSA_CHANNEL)
            app.logger.info(f'DSA subscriber started on pid={my_pid}')
            for message in pubsub.listen():
                if _stop_event.is_set():
                    break
                if message and message.get('type') == 'message':
                    try:
                        payload = json.loads(message['data'])
                        origin_pid = payload.get('_pid', 0)
                        _apply_event(payload, origin_pid)
                    except Exception as e:
                        app.logger.warning(f'DSA event apply failed: {e}')
        except Exception as e:
            app.logger.warning(f'DSA subscriber error: {e}; retrying in 5s')
            time.sleep(5)


def _resync_loop(app):
    """Periodic DB resync — safety net if Pub/Sub drops events."""
    while not _stop_event.is_set():
        if _stop_event.wait(PERIODIC_RESYNC_SECONDS):
            break
        warm_up_dsas(app)


def start_background_sync(app):
    """Start subscriber + periodic resync threads. Idempotent per-process."""
    global _subscriber_thread, _resync_thread
    if _subscriber_thread and _subscriber_thread.is_alive():
        return
    _stop_event.clear()
    _subscriber_thread = threading.Thread(
        target=_subscriber_loop, args=(app,), daemon=True, name='dsa-subscriber'
    )
    _subscriber_thread.start()
    _resync_thread = threading.Thread(
        target=_resync_loop, args=(app,), daemon=True, name='dsa-resync'
    )
    _resync_thread.start()


def stop_background_sync():
    _stop_event.set()
