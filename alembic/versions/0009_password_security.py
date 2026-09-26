"""add password change requirement to users

Revision ID: 0009_password_security
Revises: 0008_election_voting
Create Date: 2026-09-26
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0009_password_security"
down_revision = "0008_election_voting"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "must_change_password",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    # Existing accounts are already established accounts.
    # They should not be forced into the first-login password flow.
    op.alter_column(
        "users",
        "must_change_password",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column(
        "users",
        "must_change_password",
    )
