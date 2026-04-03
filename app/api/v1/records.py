from flask import jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from app.api.v1 import api_v1_bp
from app.middleware.rbac import role_required, permission_required
from app.middleware.rate_limiter import role_rate_limit
from app.schemas.record_schema import (
    RecordCreateSchema, RecordUpdateSchema, RecordResponseSchema, RecordFilterSchema
)
from app.services import record_service

record_schema = RecordResponseSchema()
records_schema = RecordResponseSchema(many=True)


@api_v1_bp.route('/records', methods=['POST'])
@jwt_required()
@role_required('manager')
@role_rate_limit
def create_record():
    """Create a financial record.
    ---
    tags: [Financial Records]
    security: [{Bearer: []}]
    parameters:
      - in: body
        name: body
        schema:
          type: object
          required: [amount, type, category, date]
          properties:
            amount: {type: string, example: "1500.00"}
            type: {type: string, enum: [income, expense]}
            category: {type: string, example: Salary}
            date: {type: string, format: date, example: "2026-03-15"}
            description: {type: string}
            tags: {type: array, items: {type: string}}
            is_recurring: {type: boolean}
    responses:
      201: {description: Record created}
      422: {description: Validation error}
    """
    data = RecordCreateSchema().load(request.get_json())
    user_id = get_jwt_identity()
    record = record_service.create_record(data, user_id)
    return jsonify({
        'record': record_schema.dump(record),
        'message': 'Record created',
    }), 201


@api_v1_bp.route('/records', methods=['GET'])
@jwt_required()
@role_required('analyst')
@role_rate_limit
def list_records():
    """List records with filters, sort, and pagination.
    ---
    tags: [Financial Records]
    security: [{Bearer: []}]
    parameters:
      - {in: query, name: type, type: string, enum: [income, expense]}
      - {in: query, name: category, type: string}
      - {in: query, name: date_from, type: string, format: date}
      - {in: query, name: date_to, type: string, format: date}
      - {in: query, name: min_amount, type: string}
      - {in: query, name: max_amount, type: string}
      - {in: query, name: sort_by, type: string, default: date}
      - {in: query, name: sort_order, type: string, default: desc}
      - {in: query, name: cursor, type: string}
      - {in: query, name: limit, type: integer, default: 20}
    responses:
      200: {description: Paginated record list}
    """
    filters = RecordFilterSchema().load(request.args.to_dict())
    items, next_cursor, has_more = record_service.get_records(filters)

    return jsonify({
        'records': records_schema.dump(items),
        'pagination': {
            'next_cursor': next_cursor,
            'has_more': has_more,
            'limit': filters.get('limit', 20),
        }
    }), 200


@api_v1_bp.route('/records/search', methods=['GET'])
@jwt_required()
@role_required('analyst')
@role_rate_limit
def search_records():
    """Trie-based search autocomplete.
    ---
    tags: [Financial Records]
    security: [{Bearer: []}]
    parameters:
      - {in: query, name: q, type: string, required: true}
      - {in: query, name: limit, type: integer, default: 10}
    responses:
      200: {description: Search suggestions}
    """
    query = request.args.get('q', '').strip()
    limit = request.args.get('limit', 10, type=int)

    if not query or len(query) < 2:
        return jsonify({'suggestions': [], 'message': 'Query must be at least 2 characters'}), 200

    suggestions = record_service.search_records(query, limit=limit)
    return jsonify({'suggestions': suggestions, 'query': query}), 200


@api_v1_bp.route('/records/<record_id>', methods=['GET'])
@jwt_required()
@role_required('analyst')
@role_rate_limit
def get_record(record_id):
    """Get a single record.
    ---
    tags: [Financial Records]
    security: [{Bearer: []}]
    parameters:
      - {in: path, name: record_id, type: string, required: true}
    responses:
      200: {description: Record details}
      404: {description: Record not found}
    """
    record = record_service.get_record_by_id(record_id)
    return jsonify({'record': record_schema.dump(record)}), 200


@api_v1_bp.route('/records/<record_id>', methods=['PUT'])
@jwt_required()
@role_required('manager')
@role_rate_limit
def update_record(record_id):
    """Update a record.
    ---
    tags: [Financial Records]
    security: [{Bearer: []}]
    parameters:
      - {in: path, name: record_id, type: string, required: true}
      - in: body
        name: body
        schema:
          type: object
          properties:
            amount: {type: string}
            type: {type: string, enum: [income, expense]}
            category: {type: string}
            date: {type: string, format: date}
            description: {type: string}
            tags: {type: array, items: {type: string}}
    responses:
      200: {description: Record updated}
    """
    data = RecordUpdateSchema().load(request.get_json())
    record = record_service.update_record(record_id, data)
    return jsonify({'record': record_schema.dump(record), 'message': 'Record updated'}), 200


@api_v1_bp.route('/records/<record_id>', methods=['DELETE'])
@jwt_required()
@role_required('manager')
@role_rate_limit
def delete_record(record_id):
    """Delete a record (soft for Manager, hard with permission).
    ---
    tags: [Financial Records]
    security: [{Bearer: []}]
    parameters:
      - {in: path, name: record_id, type: string, required: true}
      - {in: query, name: hard, type: boolean, default: false}
    responses:
      200: {description: Record deleted}
    """
    hard = request.args.get('hard', 'false').lower() == 'true'
    claims = get_jwt()

    if hard:
        # Hard delete requires Admin+ (hierarchy_level >= 4)
        if claims.get('hierarchy_level', 0) < 4:
            return jsonify({'error': 'Hard delete requires Admin role'}), 403
        record_service.hard_delete_record(record_id)
        return jsonify({'message': 'Record permanently deleted'}), 200

    record_service.soft_delete_record(record_id)
    return jsonify({'message': 'Record soft deleted'}), 200
