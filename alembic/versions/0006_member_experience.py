"""member experience, notifications and preferences"""
from alembic import op
import sqlalchemy as sa

revision = "0006_member_experience"
down_revision = "0005_governance"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("notifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("member_id", sa.String(36), sa.ForeignKey("members.id")),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("notification_type", sa.String(50), nullable=False),
        sa.Column("priority", sa.String(20), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_notifications_member_id", "notifications", ["member_id"])
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_notification_type", "notifications", ["notification_type"])
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])
    op.create_table("notification_preferences",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("in_app_enabled", sa.Boolean(), nullable=False),
        sa.Column("email_enabled", sa.Boolean(), nullable=False),
        sa.Column("dues_enabled", sa.Boolean(), nullable=False),
        sa.Column("savings_enabled", sa.Boolean(), nullable=False),
        sa.Column("loans_enabled", sa.Boolean(), nullable=False),
        sa.Column("welfare_enabled", sa.Boolean(), nullable=False),
        sa.Column("governance_enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_notification_preferences_user_id", "notification_preferences", ["user_id"], unique=True)

def downgrade():
    op.drop_table("notification_preferences")
    op.drop_table("notifications")
