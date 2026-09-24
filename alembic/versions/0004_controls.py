"""financial controls, reversals, audit hash chain and webhook verification"""
from alembic import op
import sqlalchemy as sa

revision = "0004_controls"
down_revision = "0003_operations"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("financial_transactions") as batch:
        batch.add_column(sa.Column("reversed_by_transaction_id", sa.String(36)))
        batch.add_column(sa.Column("reversal_of_transaction_id", sa.String(36)))
        batch.create_foreign_key(
            "fk_financial_transactions_reversed_by",
            "financial_transactions",
            ["reversed_by_transaction_id"],
            ["id"],
        )
        batch.create_foreign_key(
            "fk_financial_transactions_reversal_of",
            "financial_transactions",
            ["reversal_of_transaction_id"],
            ["id"],
        )

    with op.batch_alter_table("audit_logs") as batch:
        batch.add_column(sa.Column("previous_hash", sa.String(64)))
        batch.add_column(sa.Column("entry_hash", sa.String(64), nullable=False, server_default="pending"))

    with op.batch_alter_table("payment_webhook_events") as batch:
        batch.add_column(sa.Column("signature", sa.String(255)))
        batch.add_column(sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("processed_at", sa.DateTime(timezone=True)))



def downgrade():
    with op.batch_alter_table("payment_webhook_events") as batch:
        batch.drop_column("processed_at")
        batch.drop_column("verified")
        batch.drop_column("signature")
    with op.batch_alter_table("audit_logs") as batch:
        batch.drop_column("entry_hash")
        batch.drop_column("previous_hash")
    with op.batch_alter_table("financial_transactions") as batch:
        batch.drop_constraint("fk_financial_transactions_reversal_of", type_="foreignkey")
        batch.drop_constraint("fk_financial_transactions_reversed_by", type_="foreignkey")
        batch.drop_column("reversal_of_transaction_id")
        batch.drop_column("reversed_by_transaction_id")
