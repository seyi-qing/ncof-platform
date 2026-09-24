from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Attendance, Meeting, Member, User
from app.schemas import MeetingCreate, AttendanceIn
from app.security import require_roles

router = APIRouter()

@router.get("")
def meetings(db: Session = Depends(get_db), _: User = Depends(require_roles("admin","executive","secretary","member"))):
    return list(db.scalars(select(Meeting).order_by(Meeting.meeting_date.desc())).all())

@router.post("", status_code=201)
def create_meeting(payload: MeetingCreate, db: Session = Depends(get_db), _: User = Depends(require_roles("admin","executive","secretary"))):
    meeting = Meeting(id=str(uuid4()), title=payload.title, meeting_date=payload.meeting_date, location=payload.location)
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    return meeting

@router.post("/{meeting_id}/attendance", status_code=201)
def record_attendance(
    meeting_id: str,
    payload: AttendanceIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin","executive","secretary")),
):
    if not db.get(Meeting, meeting_id):
        raise HTTPException(404, "Meeting not found")
    if not db.get(Member, payload.member_id):
        raise HTTPException(404, "Member not found")
    existing = db.scalar(select(Attendance).where(
        Attendance.meeting_id == meeting_id,
        Attendance.member_id == payload.member_id
    ))
    if existing:
        existing.status = payload.status
        existing.recorded_by = user.id
    else:
        db.add(Attendance(meeting_id=meeting_id, member_id=payload.member_id, status=payload.status, recorded_by=user.id))
    db.commit()
    return {"status": payload.status}
