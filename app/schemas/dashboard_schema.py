from marshmallow import Schema, fields, validate


class SummaryQuerySchema(Schema):
    date_from = fields.Date()
    date_to = fields.Date()


class TrendQuerySchema(Schema):
    period = fields.String(load_default='monthly', validate=validate.OneOf(['weekly', 'monthly']))
    months = fields.Integer(load_default=6, validate=validate.Range(min=1, max=24))


class RecentQuerySchema(Schema):
    limit = fields.Integer(load_default=10, validate=validate.Range(min=1, max=50))
