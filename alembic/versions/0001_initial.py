"""initial core schema

Only creates the tables that existed before the feature migrations.  Later
migrations own their feature tables so a fresh database can be upgraded
deterministically.
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False, server_default="member"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_role", "users", ["role"])

    op.create_table(
        "members",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), unique=True),
        sa.Column("member_no", sa.String(40), nullable=False, unique=True),
        sa.Column("full_name", sa.String(160), nullable=False),
        sa.Column("phone", sa.String(40)),
        sa.Column("email", sa.String(320)),
        sa.Column("membership_status", sa.String(30), nullable=False, server_default="active"),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_members_full_name", "members", ["full_name"])
    op.create_index("ix_members_membership_status", "members", ["membership_status"])

    op.create_table(
        "meetings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("meeting_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("location", sa.String(255)),
        sa.Column("status", sa.String(30), nullable=False, server_default="scheduled"),
    )
    op.create_index("ix_meetings_meeting_date", "meetings", ["meeting_date"])

    op.create_table(
        "attendance",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("meeting_id", sa.String(36), sa.ForeignKey("meetings.id"), nullable=False),
        sa.Column("member_id", sa.String(36), sa.ForeignKey("members.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="present"),
        sa.Column("checked_in_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_by", sa.String(36), sa.ForeignKey("users.id")),
        sa.UniqueConstraint("meeting_id", "member_id", name="uq_attendance_meeting_member"),
    )

    op.create_table(
        "accounts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("member_id", sa.String(36), sa.ForeignKey("members.id"), nullable=False),
        sa.Column("account_type", sa.String(30), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="NGN"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.UniqueConstraint("member_id", "account_type", name="uq_member_account_type"),
    )
    op.create_index("ix_accounts_member_id", "accounts", ["member_id"])
    op.create_index("ix_accounts_account_type", "accounts", ["account_type"])

    op.create_table(
        "financial_transactions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("reference", sa.String(80), nullable=False, unique=True),
        sa.Column("member_id", sa.String(36), sa.ForeignKey("members.id"), nullable=False),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("transaction_type", sa.String(40), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("status", sa.String(20), nullable=False, server_default="posted"),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_financial_transactions_member_id", "financial_transactions", ["member_id"])
    op.create_index("ix_financial_transactions_account_id", "financial_transactions", ["account_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(80), nullable=False),
        sa.Column("entity_id", sa.String(36)),
        sa.Column("before_json", sa.Text()),
        sa.Column("after_json", sa.Text()),
        sa.Column("ip_address", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade():
    op.drop_table("audit_logs")
    op.drop_table("financial_transactions")
    op.drop_table("accounts")
    op.drop_table("attendance")
    op.drop_table("meetings")
    op.drop_table("members")
    op.drop_table("users")
