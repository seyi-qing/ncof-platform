"""add production election positions, participation, secret ballots and selections"""
from alembic import op
import sqlalchemy as sa
from uuid import uuid4

revision = "0008_election_voting"
down_revision = "0007_merge"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "election_positions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("election_id", sa.String(36), sa.ForeignKey("elections.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_selections", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("election_id", "name", name="uq_election_position_name"),
    )
    op.create_index("ix_election_positions_election_id", "election_positions", ["election_id"])

    op.add_column("election_candidates", sa.Column("position_id", sa.String(36), nullable=True))
    op.create_foreign_key("fk_election_candidates_position", "election_candidates", "election_positions", ["position_id"], ["id"])
    op.create_index("ix_election_candidates_position_id", "election_candidates", ["position_id"])

    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT DISTINCT election_id, position FROM election_candidates")).mappings().all()
    for row in rows:
        pos_id = str(uuid4())
        conn.execute(
            sa.text("INSERT INTO election_positions (id, election_id, name, description, sort_order, max_selections, created_at) VALUES (:id,:eid,:name,NULL,0,1,NOW())"),
            {"id": pos_id, "eid": row["election_id"], "name": row["position"]},
        )
        conn.execute(
            sa.text("UPDATE election_candidates SET position_id=:pid WHERE election_id=:eid AND position=:name"),
            {"pid": pos_id, "eid": row["election_id"], "name": row["position"]},
        )

    op.create_table(
        "election_participation",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("election_id", sa.String(36), sa.ForeignKey("elections.id"), nullable=False),
        sa.Column("member_id", sa.String(36), sa.ForeignKey("members.id"), nullable=False),
        sa.Column("voted_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("election_id", "member_id", name="uq_election_participation_member"),
    )
    op.create_index("ix_election_participation_election_id", "election_participation", ["election_id"])
    op.create_index("ix_election_participation_member_id", "election_participation", ["member_id"])

    op.create_table(
        "election_ballots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("election_id", sa.String(36), sa.ForeignKey("elections.id"), nullable=False),
        sa.Column("receipt_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("cast_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_election_ballots_election_id", "election_ballots", ["election_id"])
    op.create_index("ix_election_ballots_receipt_hash", "election_ballots", ["receipt_hash"], unique=True)

    op.create_table(
        "election_ballot_selections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("ballot_id", sa.String(36), sa.ForeignKey("election_ballots.id"), nullable=False),
        sa.Column("position_id", sa.String(36), sa.ForeignKey("election_positions.id"), nullable=False),
        sa.Column("candidate_id", sa.String(36), sa.ForeignKey("election_candidates.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("ballot_id", "position_id", name="uq_ballot_position"),
    )
    op.create_index("ix_election_ballot_selections_ballot_id", "election_ballot_selections", ["ballot_id"])
    op.create_index("ix_election_ballot_selections_position_id", "election_ballot_selections", ["position_id"])
    op.create_index("ix_election_ballot_selections_candidate_id", "election_ballot_selections", ["candidate_id"])

def downgrade():
    op.drop_table("election_ballot_selections")
    op.drop_table("election_ballots")
    op.drop_table("election_participation")
    op.drop_index("ix_election_candidates_position_id", table_name="election_candidates")
    op.drop_constraint("fk_election_candidates_position", "election_candidates", type_="foreignkey")
    op.drop_column("election_candidates", "position_id")
    op.drop_table("election_positions")
