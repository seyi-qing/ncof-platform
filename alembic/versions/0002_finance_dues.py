from alembic import op
import sqlalchemy as sa

revision = "0002_finance_dues"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "ledger_entries",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("transaction_id", sa.String(length=36), sa.ForeignKey("financial_transactions.id"), nullable=False),
        sa.Column("ledger_account", sa.String(length=80), nullable=False),
        sa.Column("debit", sa.Numeric(18,2), nullable=False, server_default="0"),
        sa.Column("credit", sa.Numeric(18,2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ledger_entries_transaction_id", "ledger_entries", ["transaction_id"])
    op.create_index("ix_ledger_entries_ledger_account", "ledger_entries", ["ledger_account"])
    op.create_table(
        "monthly_dues",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("member_id", sa.String(length=36), sa.ForeignKey("members.id"), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("amount_due", sa.Numeric(18,2), nullable=False),
        sa.Column("amount_paid", sa.Numeric(18,2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="unpaid"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("member_id", "year", "month", name="uq_member_dues_month"),
    )
    op.create_index("ix_monthly_dues_member_id", "monthly_dues", ["member_id"])
    op.create_index("ix_monthly_dues_year", "monthly_dues", ["year"])
    op.create_index("ix_monthly_dues_month", "monthly_dues", ["month"])

def downgrade():
    op.drop_index("ix_monthly_dues_month", table_name="monthly_dues")
    op.drop_index("ix_monthly_dues_year", table_name="monthly_dues")
    op.drop_index("ix_monthly_dues_member_id", table_name="monthly_dues")
    op.drop_table("monthly_dues")
    op.drop_index("ix_ledger_entries_ledger_account", table_name="ledger_entries")
    op.drop_index("ix_ledger_entries_transaction_id", table_name="ledger_entries")
    op.drop_table("ledger_entries")
