from marshmallow import Schema, fields, validate, validates, ValidationError


class RegisterSchema(Schema):
    username = fields.String(
        required=True,
        validate=[validate.Length(min=3, max=80), validate.Regexp(
            r'^[a-zA-Z0-9_]+$', error='Username must be alphanumeric with underscores only'
        )]
    )
    email = fields.Email(required=True)
    password = fields.String(
        required=True, load_only=True,
        validate=validate.Length(min=8, max=128)
    )

    @validates('password')
    def validate_password_strength(self, value):
        if not any(c.isupper() for c in value):
            raise ValidationError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in value):
            raise ValidationError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in value):
            raise ValidationError('Password must contain at least one digit')


class LoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.String(required=True, load_only=True)


class UserResponseSchema(Schema):
    id = fields.UUID(dump_only=True)
    username = fields.String()
    email = fields.Email()
    role = fields.Method('get_role')
    is_active = fields.Boolean()
    last_login = fields.DateTime()
    created_at = fields.DateTime()
    updated_at = fields.DateTime()

    def get_role(self, obj):
        return {'id': obj.role.id, 'name': obj.role.name} if obj.role else None


class UserUpdateSchema(Schema):
    username = fields.String(validate=validate.Length(min=3, max=80))
    email = fields.Email()


class RoleAssignSchema(Schema):
    role_name = fields.String(
        required=True,
        validate=validate.OneOf(['viewer', 'analyst', 'manager', 'admin', 'super_admin'])
    )


class StatusUpdateSchema(Schema):
    is_active = fields.Boolean(required=True)
