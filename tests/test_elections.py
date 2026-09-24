from datetime import datetime, timezone, timedelta

import pytest

from app.schemas import ElectionCreate, ElectionPositionCreate, CastVoteIn, VoteSelection
from app.core.config import Settings


def test_election_window_model_accepts_valid_window():
    now = datetime.now(timezone.utc)
    item = ElectionCreate(title="Annual Election", opens_at=now, closes_at=now + timedelta(hours=2))
    assert item.closes_at > item.opens_at


def test_vote_payload_supports_one_selection_per_position():
    payload = CastVoteIn(selections=[
        VoteSelection(position_id="p1", candidate_id="c1"),
        VoteSelection(position_id="p2", candidate_id="c2"),
    ])
    assert len(payload.selections) == 2


def test_position_initial_method_is_single_choice():
    position = ElectionPositionCreate(name="President")
    assert position.max_selections == 1


def test_production_secrets_must_be_distinct():
    with pytest.raises(ValueError):
        Settings(
            app_env="production",
            database_url="postgresql+psycopg://example",
            secret_key="x" * 40,
            payment_webhook_secret="x" * 40,
            audit_hash_secret="y" * 40,
            cors_origins=["https://example.com"],
        )
