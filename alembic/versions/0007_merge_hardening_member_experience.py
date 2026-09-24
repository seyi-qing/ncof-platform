"""merge hardening and member experience migration branches

Revision ID: 0007_merge_hardening_member_experience
Revises: 0006_hardening, 0006_member_experience
"""
from alembic import op

revision = "0007_merge_hardening_member_experience"
down_revision = ("0006_hardening", "0006_member_experience")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
