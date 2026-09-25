"""operations: savings withdrawals, loans, welfare claims, receipts and webhook idempotency"""
from alembic import op
import sqlalchemy as sa

revision = "0003_operations"
down_revision = "0002_finance_dues"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("withdrawal_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("member_id", sa.String(36), sa.ForeignKey("members.id"), nullable=False),
        sa.Column("amount", sa.Numeric(18,2), nullable=False),
        sa.Column("reason", sa.Text()), sa.Column("status", sa.String(20), nullable=False),
        sa.Column("requested_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("decided_by", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("decision_note", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_withdrawal_requests_member_id", "withdrawal_requests", ["member_id"])
    op.create_index("ix_withdrawal_requests_status", "withdrawal_requests", ["status"])

    op.create_table("loan_applications",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("member_id", sa.String(36), sa.ForeignKey("members.id"), nullable=False),
        sa.Column("amount", sa.Numeric(18,2), nullable=False), sa.Column("term_months", sa.Integer(), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False), sa.Column("status", sa.String(20), nullable=False),
        sa.Column("requested_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("decided_by", sa.String(36), sa.ForeignKey("users.id")), sa.Column("decision_note", sa.Text()),
        sa.Column("approved_at", sa.DateTime(timezone=True)), sa.Column("disbursed_at", sa.DateTime(timezone=True)),
        sa.Column("disbursed_transaction_id", sa.String(36), sa.ForeignKey("financial_transactions.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_loan_applications_member_id", "loan_applications", ["member_id"])
    op.create_index("ix_loan_applications_status", "loan_applications", ["status"])

    op.create_table("loan_repayment_schedules",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("loan_id", sa.String(36), sa.ForeignKey("loan_applications.id"), nullable=False),
        sa.Column("installment_no", sa.Integer(), nullable=False), sa.Column("due_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("amount_due", sa.Numeric(18,2), nullable=False), sa.Column("amount_paid", sa.Numeric(18,2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False), sa.UniqueConstraint("loan_id", "installment_no", name="uq_loan_installment"))
    op.create_index("ix_loan_repayment_schedules_loan_id", "loan_repayment_schedules", ["loan_id"])
    op.create_index("ix_loan_repayment_schedules_due_date", "loan_repayment_schedules", ["due_date"])

    op.create_table("welfare_claims",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("member_id", sa.String(36), sa.ForeignKey("members.id"), nullable=False),
        sa.Column("amount", sa.Numeric(18,2), nullable=False), sa.Column("category", sa.String(80), nullable=False), sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False), sa.Column("requested_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("decided_by", sa.String(36), sa.ForeignKey("users.id")), sa.Column("decision_note", sa.Text()),
        sa.Column("disbursed_transaction_id", sa.String(36), sa.ForeignKey("financial_transactions.id")), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_welfare_claims_member_id", "welfare_claims", ["member_id"])
    op.create_index("ix_welfare_claims_status", "welfare_claims", ["status"])

    op.create_table("receipts",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("transaction_id", sa.String(36), sa.ForeignKey("financial_transactions.id"), nullable=False, unique=True),
        sa.Column("receipt_no", sa.String(80), nullable=False, unique=True), sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_receipts_receipt_no", "receipts", ["receipt_no"])

    op.create_table("idempotency_keys",
        sa.Column("key", sa.String(120), primary_key=True), sa.Column("scope", sa.String(120), nullable=False),
        sa.Column("response_json", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_idempotency_keys_scope", "idempotency_keys", ["scope"])

    op.create_table("payment_webhook_events",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("event_id", sa.String(160), nullable=False, unique=True),
        sa.Column("provider", sa.String(50), nullable=False), sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_payment_webhook_events_event_id", "payment_webhook_events", ["event_id"])


def downgrade():
    for name in ["payment_webhook_events", "idempotency_keys", "receipts", "welfare_claims", "loan_repayment_schedules", "loan_applications", "withdrawal_requests"]:
        op.drop_table(name)
