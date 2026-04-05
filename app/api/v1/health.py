from flask import jsonify, request
from flask_jwt_extended import jwt_required

from app.api.v1 import api_v1_bp
from app.extensions import db, get_redis
from app.middleware.rbac import role_required
from app.middleware.rate_limiter import role_rate_limit
from app.models.audit_log import AuditLog


@api_v1_bp.route('/health', methods=['GET'])
def health_check():
    """Application health check.
    ---
    tags: [System]
    responses:
      200: {description: All systems healthy}
      503: {description: One or more dependencies unhealthy}
    """
    status = {'app': 'healthy'}
    overall_healthy = True

    try:
        db.session.execute(db.text('SELECT 1'))
        status['database'] = 'healthy'
    except Exception:
        status['database'] = 'unhealthy'
        overall_healthy = False

    r = get_redis()
    if r:
        try:
            r.ping()
            status['redis'] = 'healthy'
        except Exception:
            status['redis'] = 'unhealthy'
    else:
        status['redis'] = 'unavailable (running with DB fallbacks)'

    status_code = 200 if overall_healthy else 503
    return jsonify({'status': 'healthy' if overall_healthy else 'degraded', 'services': status}), status_code


@api_v1_bp.route('/audit-logs', methods=['GET'])
@jwt_required()
@role_required('admin')
@role_rate_limit
def get_audit_logs():
    """Query audit trail. Admin+ only.
    ---
    tags: [System]
    security: [{Bearer: []}]
    parameters:
      - {in: query, name: user_id, type: string}
      - {in: query, name: action, type: string}
      - {in: query, name: resource, type: string}
      - {in: query, name: limit, type: integer, default: 50}
    responses:
      200: {description: Audit logs}
    """
    query = AuditLog.query.order_by(AuditLog.timestamp.desc())

    user_id = request.args.get('user_id')
    action = request.args.get('action')
    resource = request.args.get('resource')
    limit = request.args.get('limit', 50, type=int)

    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if action:
        query = query.filter(AuditLog.action == action)
    if resource:
        query = query.filter(AuditLog.resource == resource)

    logs = query.limit(min(limit, 200)).all()

    return jsonify({
        'audit_logs': [{
            'id': str(l.id),
            'user_id': str(l.user_id) if l.user_id else None,
            'action': l.action,
            'resource': l.resource,
            'resource_id': l.resource_id,
            'old_value': l.old_value,
            'new_value': l.new_value,
            'ip_address': l.ip_address,
            'timestamp': l.timestamp.isoformat() if l.timestamp else None,
        } for l in logs],
        'count': len(logs),
    }), 200
