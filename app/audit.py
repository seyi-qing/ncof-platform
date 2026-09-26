import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog


def _json(value) -> str | None:
    if value is None:
        return None

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _hash_entry(
    *,
    entry_id: str,
    actor_user_id: str | None,
    action: str,
    entity_type: str,
    entity_id: str | None,
    before_json: str | None,
    after_json: str | None,
    ip_address: str | None,
    previous_hash: str | None,
    created_at: datetime,
) -> str:
    payload = {
        "id": entry_id,
        "actor_user_id": actor_user_id,
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "before_json": before_json,
        "after_json": after_json,
        "ip_address": ip_address,
        "previous_hash": previous_hash,
        "created_at": created_at.isoformat(),
    }

    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )

    return hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()


def write_audit(
    db: Session,
    *,
    actor_user_id: str | None,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    before=None,
    after=None,
    ip_address: str | None = None,
) -> AuditLog:
    """
    Add one entry to the audit hash chain.

    This function does not commit the transaction.
    The caller should commit the business change and
    audit entry together.
    """

    previous = db.scalar(
        select(AuditLog)
        .order_by(
            AuditLog.created_at.desc(),
            AuditLog.id.desc(),
        )
        .limit(1)
    )

    previous_hash = (
        previous.entry_hash
        if previous
        else None
    )

    before_json = _json(before)
    after_json = _json(after)

    entry = AuditLog(
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before_json=before_json,
        after_json=after_json,
        ip_address=ip_address,
        previous_hash=previous_hash,
        entry_hash="pending",
        created_at=datetime.now(timezone.utc),
    )

    db.add(entry)

    # Flush so SQLAlchemy assigns the UUID primary key
    # before calculating the immutable hash.
    db.flush()

    entry.entry_hash = _hash_entry(
        entry_id=entry.id,
        actor_user_id=entry.actor_user_id,
        action=entry.action,
        entity_type=entry.entity_type,
        entity_id=entry.entity_id,
        before_json=entry.before_json,
        after_json=entry.after_json,
        ip_address=entry.ip_address,
        previous_hash=entry.previous_hash,
        created_at=entry.created_at,
    )

    db.flush()

    return entry
