"""Common validation helpers."""

from decimal import Decimal, InvalidOperation


def validate_uuid(value):
    """Check if a string is a valid UUID v4."""
    import uuid
    try:
        uuid.UUID(str(value), version=4)
        return True
    except (ValueError, AttributeError):
        return False


def validate_positive_decimal(value):
    """Ensure a value is a positive decimal."""
    try:
        d = Decimal(str(value))
        return d > 0
    except (InvalidOperation, TypeError):
        return False
