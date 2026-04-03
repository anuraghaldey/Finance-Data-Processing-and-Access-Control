from flask import jsonify, request
from flask_jwt_extended import jwt_required

from app.api.v1 import api_v1_bp
from app.middleware.rbac import role_required
from app.middleware.rate_limiter import role_rate_limit
from app.schemas.dashboard_schema import SummaryQuerySchema, TrendQuerySchema, RecentQuerySchema
from app.services import dashboard_service


@api_v1_bp.route('/dashboard/summary', methods=['GET'])
@jwt_required()
@role_required('viewer')
@role_rate_limit
def dashboard_summary():
    """Total income, expenses, net balance.
    ---
    tags: [Dashboard]
    security: [{Bearer: []}]
    parameters:
      - {in: query, name: date_from, type: string, format: date}
      - {in: query, name: date_to, type: string, format: date}
    responses:
      200: {description: Dashboard summary}
    """
    params = SummaryQuerySchema().load(request.args.to_dict())
    result = dashboard_service.get_summary(
        date_from=params.get('date_from'),
        date_to=params.get('date_to'),
    )
    return jsonify(result), 200


@api_v1_bp.route('/dashboard/categories', methods=['GET'])
@jwt_required()
@role_required('viewer')
@role_rate_limit
def dashboard_categories():
    """Category-wise breakdown.
    ---
    tags: [Dashboard]
    security: [{Bearer: []}]
    parameters:
      - {in: query, name: date_from, type: string, format: date}
      - {in: query, name: date_to, type: string, format: date}
    responses:
      200: {description: Category breakdown}
    """
    params = SummaryQuerySchema().load(request.args.to_dict())
    result = dashboard_service.get_category_breakdown(
        date_from=params.get('date_from'),
        date_to=params.get('date_to'),
    )
    return jsonify(result), 200


@api_v1_bp.route('/dashboard/trends', methods=['GET'])
@jwt_required()
@role_required('analyst')
@role_rate_limit
def dashboard_trends():
    """Monthly/weekly trend data.
    ---
    tags: [Dashboard]
    security: [{Bearer: []}]
    parameters:
      - {in: query, name: period, type: string, enum: [monthly, weekly], default: monthly}
      - {in: query, name: months, type: integer, default: 6}
    responses:
      200: {description: Trend data}
    """
    params = TrendQuerySchema().load(request.args.to_dict())
    result = dashboard_service.get_trends(
        period=params.get('period', 'monthly'),
        months=params.get('months', 6),
    )
    return jsonify(result), 200


@api_v1_bp.route('/dashboard/recent', methods=['GET'])
@jwt_required()
@role_required('viewer')
@role_rate_limit
def dashboard_recent():
    """Recent activity feed.
    ---
    tags: [Dashboard]
    security: [{Bearer: []}]
    parameters:
      - {in: query, name: limit, type: integer, default: 10}
    responses:
      200: {description: Recent activity}
    """
    params = RecentQuerySchema().load(request.args.to_dict())
    result = dashboard_service.get_recent_activity(limit=params.get('limit', 10))
    return jsonify({'recent_activity': result}), 200
