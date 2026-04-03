"""
Cursor-based pagination.

Uses keyset pagination instead of OFFSET for consistent O(1) performance
regardless of page number. OFFSET-based pagination degrades with large
offsets because the DB still scans skipped rows.

Cursor is a base64-encoded string of the last item's sort key,
allowing the next page to start exactly after it.
"""

import base64
import json

from flask import request


def encode_cursor(data):
    """Encode pagination data into an opaque cursor string."""
    return base64.urlsafe_b64encode(json.dumps(data).encode()).decode()


def decode_cursor(cursor):
    """Decode a cursor string back into pagination data."""
    if not cursor:
        return None
    try:
        return json.loads(base64.urlsafe_b64decode(cursor.encode()))
    except Exception:
        return None


def paginate_query(query, model, sort_by='created_at', sort_order='desc', cursor=None, limit=20):
    """
    Apply cursor-based pagination to a SQLAlchemy query.

    Returns (items, next_cursor, has_more).
    """
    sort_col = getattr(model, sort_by, model.created_at)
    id_col = model.id

    # Apply cursor filter
    cursor_data = decode_cursor(cursor)
    if cursor_data:
        cursor_value = cursor_data.get('value')
        cursor_id = cursor_data.get('id')

        if sort_order == 'desc':
            query = query.filter(
                db_or(
                    sort_col < cursor_value,
                    db_and(sort_col == cursor_value, id_col > cursor_id),
                )
            )
        else:
            query = query.filter(
                db_or(
                    sort_col > cursor_value,
                    db_and(sort_col == cursor_value, id_col > cursor_id),
                )
            )

    # Apply sort
    if sort_order == 'desc':
        query = query.order_by(sort_col.desc(), id_col.asc())
    else:
        query = query.order_by(sort_col.asc(), id_col.asc())

    # Fetch one extra to check if there are more
    items = query.limit(limit + 1).all()
    has_more = len(items) > limit
    items = items[:limit]

    # Build next cursor
    next_cursor = None
    if has_more and items:
        last = items[-1]
        last_value = getattr(last, sort_by)
        # Convert to string for JSON serialization
        if hasattr(last_value, 'isoformat'):
            last_value = last_value.isoformat()
        else:
            last_value = str(last_value)
        next_cursor = encode_cursor({'value': last_value, 'id': str(last.id)})

    return items, next_cursor, has_more


def db_or(*conditions):
    from sqlalchemy import or_
    return or_(*conditions)


def db_and(*conditions):
    from sqlalchemy import and_
    return and_(*conditions)
