"""association governance, committees, minutes, resolutions, elections and announcements"""
from alembic import op
import sqlalchemy as sa

revision = "0005_governance"
down_revision = "0004_controls"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("committees",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text()), sa.Column("status", sa.String(20), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_committees_name", "committees", ["name"], unique=True)
    op.create_table("committee_members",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("committee_id", sa.String(36), sa.ForeignKey("committees.id"), nullable=False),
        sa.Column("member_id", sa.String(36), sa.ForeignKey("members.id"), nullable=False), sa.Column("position", sa.String(80), nullable=False),
        sa.Column("start_date", sa.DateTime(timezone=True)), sa.Column("end_date", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("committee_id", "member_id", name="uq_committee_member"))
    op.create_index("ix_committee_members_committee_id", "committee_members", ["committee_id"])
    op.create_index("ix_committee_members_member_id", "committee_members", ["member_id"])
    op.create_table("meeting_agenda_items",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("meeting_id", sa.String(36), sa.ForeignKey("meetings.id"), nullable=False),
        sa.Column("item_no", sa.Integer(), nullable=False), sa.Column("title", sa.String(200), nullable=False), sa.Column("description", sa.Text()),
        sa.Column("presenter", sa.String(160)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("meeting_id", "item_no", name="uq_meeting_agenda_no"))
    op.create_index("ix_meeting_agenda_items_meeting_id", "meeting_agenda_items", ["meeting_id"])
    op.create_table("meeting_minutes",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("meeting_id", sa.String(36), sa.ForeignKey("meetings.id"), nullable=False, unique=True),
        sa.Column("prepared_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False), sa.Column("approved_by", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("content", sa.Text(), nullable=False), sa.Column("status", sa.String(20), nullable=False), sa.Column("approved_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_meeting_minutes_status", "meeting_minutes", ["status"])
    op.create_table("resolutions",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("meeting_id", sa.String(36), sa.ForeignKey("meetings.id")), sa.Column("reference", sa.String(80), nullable=False, unique=True),
        sa.Column("title", sa.String(200), nullable=False), sa.Column("text", sa.Text(), nullable=False), sa.Column("status", sa.String(20), nullable=False),
        sa.Column("proposed_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False), sa.Column("adopted_by", sa.String(36), sa.ForeignKey("users.id")), sa.Column("adopted_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_resolutions_meeting_id", "resolutions", ["meeting_id"])
    op.create_index("ix_resolutions_status", "resolutions", ["status"])
    op.create_index("ix_resolutions_reference", "resolutions", ["reference"], unique=True)
    op.create_table("action_items",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("resolution_id", sa.String(36), sa.ForeignKey("resolutions.id")), sa.Column("meeting_id", sa.String(36), sa.ForeignKey("meetings.id")),
        sa.Column("title", sa.String(200), nullable=False), sa.Column("description", sa.Text()), sa.Column("assignee_member_id", sa.String(36), sa.ForeignKey("members.id"), nullable=False),
        sa.Column("due_date", sa.DateTime(timezone=True)), sa.Column("status", sa.String(20), nullable=False), sa.Column("notes", sa.Text()), sa.Column("completed_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_action_items_resolution_id", "action_items", ["resolution_id"]); op.create_index("ix_action_items_meeting_id", "action_items", ["meeting_id"]); op.create_index("ix_action_items_assignee_member_id", "action_items", ["assignee_member_id"]); op.create_index("ix_action_items_status", "action_items", ["status"])
    op.create_table("elections",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("title", sa.String(200), nullable=False), sa.Column("description", sa.Text()), sa.Column("opens_at", sa.DateTime(timezone=True), nullable=False), sa.Column("closes_at", sa.DateTime(timezone=True), nullable=False), sa.Column("status", sa.String(20), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_elections_status", "elections", ["status"])
    op.create_table("election_candidates",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("election_id", sa.String(36), sa.ForeignKey("elections.id"), nullable=False), sa.Column("member_id", sa.String(36), sa.ForeignKey("members.id"), nullable=False), sa.Column("position", sa.String(100), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("election_id", "member_id", "position", name="uq_election_candidate"))
    op.create_index("ix_election_candidates_election_id", "election_candidates", ["election_id"]); op.create_index("ix_election_candidates_member_id", "election_candidates", ["member_id"])
    op.create_table("association_documents",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("title", sa.String(200), nullable=False), sa.Column("document_type", sa.String(80), nullable=False), sa.Column("storage_url", sa.String(1000), nullable=False), sa.Column("description", sa.Text()), sa.Column("uploaded_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_association_documents_document_type", "association_documents", ["document_type"])
    op.create_table("announcements",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("title", sa.String(200), nullable=False), sa.Column("body", sa.Text(), nullable=False), sa.Column("audience", sa.String(50), nullable=False), sa.Column("published", sa.Boolean(), nullable=False), sa.Column("published_by", sa.String(36), sa.ForeignKey("users.id")), sa.Column("published_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))


def downgrade():
    for table in ["announcements", "association_documents", "election_candidates", "elections", "action_items", "resolutions", "meeting_minutes", "meeting_agenda_items", "committee_members", "committees"]:
        op.drop_table(table)
