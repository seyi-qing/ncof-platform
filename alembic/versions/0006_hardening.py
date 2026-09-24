"""security hardening: refresh tokens and login throttling"""
from alembic import op
import sqlalchemy as sa
revision = "0006_hardening"
down_revision = "0005_governance"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("refresh_tokens",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)), sa.Column("replaced_by_id", sa.String(36), sa.ForeignKey("refresh_tokens.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True)
    op.create_index("ix_refresh_tokens_expires_at", "refresh_tokens", ["expires_at"])
    op.create_table("login_attempts",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("email", sa.String(320), nullable=False), sa.Column("ip_address", sa.String(64)),
        sa.Column("failed_count", sa.Integer(), nullable=False), sa.Column("locked_until", sa.DateTime(timezone=True)), sa.Column("last_failed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("email", "ip_address", name="uq_login_attempt_email_ip"))
    op.create_index("ix_login_attempts_email", "login_attempts", ["email"]); op.create_index("ix_login_attempts_ip_address", "login_attempts", ["ip_address"])

def downgrade():
    op.drop_table("login_attempts"); op.drop_table("refresh_tokens")
