"""Supplemental governance endpoints (polish 3)."""
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import (
    User, Member, Committee, CommitteeMember, Announcement, Notification,
)
from app.security import require_roles

router = APIRouter()
MANAGERS = ("admin", "executive", "secretary")

def now():
    return datetime.now(timezone.utc)

@router.get("/committees/{committee_id}")
def get_committee(committee_id: str, db: Session = Depends(get_db), _: User = Depends(require_roles(*MANAGERS, "member"))):
    item = db.get(Committee, committee_id)
    if not item:
        raise HTTPException(404, "Committee not found")
    members = list(db.scalars(select(CommitteeMember).where(CommitteeMember.committee_id == committee_id)).all())
    return {
        "id": item.id,
        "name": item.name,
        "description": item.description,
        "status": item.status,
        "members": [
            {"id": m.id, "member_id": m.member_id, "position": m.position, "start_date": m.start_date, "end_date": m.end_date}
            for m in members
        ],
    }

@router.patch("/committees/{committee_id}")
def update_committee(committee_id: str, payload: dict, db: Session = Depends(get_db), _: User = Depends(require_roles(*MANAGERS))):
    item = db.get(Committee, committee_id)
    if not item:
        raise HTTPException(404, "Committee not found")
    if "name" in payload and payload["name"]:
        item.name = str(payload["name"]).strip()
    if "description" in payload:
        item.description = payload["description"]
    if "status" in payload and payload["status"] in ("active", "archived"):
        item.status = payload["status"]
    db.commit()
    db.refresh(item)
    return item

@router.get("/announcements/all")
def list_all_announcements(db: Session = Depends(get_db), user: User = Depends(require_roles(*MANAGERS))):
    return list(db.scalars(select(Announcement).order_by(Announcement.id.desc())).all())

@router.post("/announcements/{announcement_id}/publish")
def publish_announcement(announcement_id: str, db: Session = Depends(get_db), user: User = Depends(require_roles(*MANAGERS))):
    item = db.get(Announcement, announcement_id)
    if not item:
        raise HTTPException(404, "Announcement not found")
    if item.published:
        return item
    item.published = True
    item.published_by = user.id
    item.published_at = now()
    members = list(db.scalars(select(Member).where(Member.membership_status == "active", Member.user_id.is_not(None))).all())
    db.add_all([
        Notification(id=str(uuid4()), member_id=m.id, user_id=m.user_id, title=item.title, body=item.body, notification_type="governance", priority="normal")
        for m in members
    ])
    db.commit()
    db.refresh(item)
    return item
