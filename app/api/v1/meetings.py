from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Attendance, Meeting, Member, User
from app.schemas import MeetingCreate, MeetingUpdate, AttendanceIn
from app.security import require_roles

router = APIRouter()

STAFF = ("admin", "executive", "secretary")


def _attendance_rows(db, attendance):
    rows = []
    for a in attendance:
        m = db.get(Member, a.member_id)
        rows.append({
            "id": getattr(a, "id", None),
            "member_id": a.member_id,
            "member_name": m.full_name if m else None,
            "status": a.status,
            "recorded_by": getattr(a, "recorded_by", None),
        })
    return rows


@router.get("")
def meetings(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*STAFF, "member")),
):
    return list(db.scalars(select(Meeting).order_by(Meeting.meeting_date.desc())).all())


@router.get("/{meeting_id}")
def get_meeting(
    meeting_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*STAFF, "member")),
):
    meeting = db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(404, "Meeting not found")
    attendance = list(
        db.scalars(
            select(Attendance).where(Attendance.meeting_id == meeting_id)
        ).all()
    )
    return {
        "id": meeting.id,
        "title": meeting.title,
        "meeting_date": meeting.meeting_date,
        "location": meeting.location,
        "created_at": getattr(meeting, "created_at", None),
        "attendance": _attendance_rows(db, attendance),
    }


@router.post("", status_code=201)
def create_meeting(
    payload: MeetingCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*STAFF)),
):
    item = Meeting(
        id=str(uuid4()),
        title=payload.title,
        meeting_date=payload.meeting_date,
        location=payload.location,
        created_by=user.id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/{meeting_id}")
def update_meeting(
    meeting_id: str,
    payload: MeetingUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*STAFF)),
):
    item = db.get(Meeting, meeting_id)
    if not item:
        raise HTTPException(404, "Meeting not found")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(item, k, v)
    db.commit()
    db.refresh(item)
    return item


@router.get("/{meeting_id}/attendance")
def list_attendance(
    meeting_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*STAFF, "member")),
):
    if not db.get(Meeting, meeting_id):
        raise HTTPException(404, "Meeting not found")
    attendance = list(
        db.scalars(select(Attendance).where(Attendance.meeting_id == meeting_id)).all()
    )
    return _attendance_rows(db, attendance)


@router.post("/{meeting_id}/attendance", status_code=201)
def record_attendance(
    meeting_id: str,
    payload: AttendanceIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*STAFF)),
):
    if not db.get(Meeting, meeting_id):
        raise HTTPException(404, "Meeting not found")
    if not db.get(Member, payload.member_id):
        raise HTTPException(404, "Member not found")
    existing = db.scalar(
        select(Attendance).where(
            Attendance.meeting_id == meeting_id,
            Attendance.member_id == payload.member_id,
        )
    )
    if existing:
        existing.status = payload.status
        existing.recorded_by = user.id
        db.commit()
        db.refresh(existing)
        return existing
    item = Attendance(
        id=str(uuid4()),
        meeting_id=meeting_id,
        member_id=payload.member_id,
        status=payload.status,
        recorded_by=user.id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
