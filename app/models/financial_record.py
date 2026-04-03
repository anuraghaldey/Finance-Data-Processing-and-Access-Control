import uuid

from sqlalchemy.dialects.postgresql import UUID, ARRAY

from app.extensions import db


class FinancialRecord(db.Model):
    __tablename__ = 'financial_records'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Numeric(15, 2), nullable=False)
    type = db.Column(db.String(10), nullable=False)  # 'income' or 'expense'
    category = db.Column(db.String(50), nullable=False)
    date = db.Column(db.Date, nullable=False)
    description = db.Column(db.Text, nullable=True)
    tags = db.Column(ARRAY(db.String(50)), nullable=True, default=[])
    is_recurring = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())
    deleted_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship('User', back_populates='records')

    __table_args__ = (
        db.CheckConstraint("type IN ('income', 'expense')", name='ck_record_type'),
        db.CheckConstraint('amount > 0', name='ck_record_amount_positive'),
        db.Index('idx_records_date', 'date'),
        db.Index('idx_records_category', 'category'),
        db.Index('idx_records_type_date', 'type', 'date'),
        db.Index('idx_records_user', 'user_id'),
        db.Index('idx_records_deleted', 'deleted_at'),
    )

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    def __repr__(self):
        return f'<FinancialRecord {self.id} {self.type} {self.amount}>'
