from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Member, User
from app.schemas import MemberCreate, MemberOut
from app.security import require_roles, current_user

router = APIRouter()

@router.get("/me", response_model=MemberOut)
def my_member_profile(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    member = db.scalar(select(Member).where(Member.user_id == user.id))
    if not member:
        raise HTTPException(404, "Member profile not linked to this account")
    return member

@router.get("", response_model=list[MemberOut])
def list_members(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "executive", "secretary", "treasurer", "auditor")),
):
    return list(db.scalars(select(Member).order_by(Member.full_name)).all())

@router.post("", response_model=MemberOut, status_code=201)
def create_member(
    payload: MemberCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "executive", "secretary")),
):
    if payload.email:
        duplicate = db.scalar(select(Member).where(Member.email == str(payload.email).lower()))
        if duplicate:
            raise HTTPException(409, "A member with this email already exists")
    member = Member(
        member_no=f"NCOF-{uuid4().hex[:10].upper()}",
        full_name=payload.full_name,
        email=str(payload.email).lower() if payload.email else None,
        phone=payload.phone,
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return member
