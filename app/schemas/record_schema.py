from marshmallow import Schema, fields, validate


class RecordCreateSchema(Schema):
    amount = fields.Decimal(required=True, as_string=True, places=2)
    type = fields.String(required=True, validate=validate.OneOf(['income', 'expense']))
    category = fields.String(required=True, validate=validate.Length(min=1, max=50))
    date = fields.Date(required=True)
    description = fields.String(validate=validate.Length(max=500))
    tags = fields.List(fields.String(validate=validate.Length(max=50)), load_default=[])
    is_recurring = fields.Boolean(load_default=False)


class RecordUpdateSchema(Schema):
    amount = fields.Decimal(as_string=True, places=2)
    type = fields.String(validate=validate.OneOf(['income', 'expense']))
    category = fields.String(validate=validate.Length(min=1, max=50))
    date = fields.Date()
    description = fields.String(validate=validate.Length(max=500))
    tags = fields.List(fields.String(validate=validate.Length(max=50)))
    is_recurring = fields.Boolean()


class RecordResponseSchema(Schema):
    id = fields.UUID(dump_only=True)
    user_id = fields.UUID()
    amount = fields.Decimal(as_string=True, places=2)
    type = fields.String()
    category = fields.String()
    date = fields.Date()
    description = fields.String()
    tags = fields.List(fields.String())
    is_recurring = fields.Boolean()
    created_at = fields.DateTime()
    updated_at = fields.DateTime()


class RecordFilterSchema(Schema):
    type = fields.String(validate=validate.OneOf(['income', 'expense']))
    category = fields.String()
    date_from = fields.Date()
    date_to = fields.Date()
    min_amount = fields.Decimal(as_string=True)
    max_amount = fields.Decimal(as_string=True)
    is_recurring = fields.Boolean()
    cursor = fields.String()  # cursor-based pagination
    limit = fields.Integer(load_default=20, validate=validate.Range(min=1, max=100))
    sort_by = fields.String(load_default='date', validate=validate.OneOf(['date', 'amount', 'category', 'created_at']))
    sort_order = fields.String(load_default='desc', validate=validate.OneOf(['asc', 'desc']))
