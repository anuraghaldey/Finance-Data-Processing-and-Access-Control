from flask import request
from flask_jwt_extended import get_jwt_identity

from app.extensions import db
from app.models.audit_log import AuditLog


def log_audit(action, resource, resource_id=None, old_value=None, new_value=None, user_id=None):
    """Log an audit event for any write operation."""
    if user_id is None:
        try:
            user_id = get_jwt_identity()
        except Exception:
            user_id = None

    audit = AuditLog(
        user_id=user_id,
        action=action,
        resource=resource,
        resource_id=str(resource_id) if resource_id else None,
        old_value=old_value,
        new_value=new_value,
        ip_address=request.remote_addr if request else None,
    )
    db.session.add(audit)
    # Committed as part of the caller's transaction
