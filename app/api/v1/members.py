from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import write_audit
from app.db import get_db
from app.models import Member, User
from app.schemas import (
    MemberCreate,
    MemberOut,
    MemberAccountCreate,
    MemberAccountOut,
)
from app.security import require_roles, current_user, hash_password

router = APIRouter()


@router.get("/me", response_model=MemberOut)
def my_member_profile(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    member = db.scalar(
        select(Member).where(Member.user_id == user.id)
    )

    if not member:
        raise HTTPException(
            404,
            "Member profile not linked to this account",
        )

    return MemberOut(
        id=member.id,
        member_no=member.member_no,
        full_name=member.full_name,
        email=member.email,
        phone=member.phone,
        membership_status=member.membership_status,
        joined_at=member.joined_at,
        has_login_account=bool(member.user_id),
    )


@router.get("", response_model=list[MemberOut])
def list_members(
    db: Session = Depends(get_db),
    _: User = Depends(
        require_roles(
            "admin",
            "executive",
            "secretary",
            "treasurer",
            "auditor",
        )
    ),
):
    members = list(
        db.scalars(
            select(Member).order_by(Member.full_name)
        ).all()
    )

    return [
        MemberOut(
            id=member.id,
            member_no=member.member_no,
            full_name=member.full_name,
            email=member.email,
            phone=member.phone,
            membership_status=member.membership_status,
            joined_at=member.joined_at,
            has_login_account=bool(member.user_id),
        )
        for member in members
    ]


@router.post(
    "",
    response_model=MemberOut,
    status_code=201,
)
def create_member(
    payload: MemberCreate,
    db: Session = Depends(get_db),
    _: User = Depends(
        require_roles(
            "admin",
            "executive",
            "secretary",
        )
    ),
):
    if payload.email:
        email = str(payload.email).lower().strip()

        duplicate = db.scalar(
            select(Member).where(Member.email == email)
        )

        if duplicate:
            raise HTTPException(
                409,
                "A member with this email already exists",
            )

    member = Member(
        member_no=f"NCOF-{uuid4().hex[:10].upper()}",
        full_name=payload.full_name,
        email=(
            str(payload.email).lower().strip()
            if payload.email
            else None
        ),
        phone=payload.phone,
    )

    db.add(member)
    db.commit()
    db.refresh(member)

    return MemberOut(
        id=member.id,
        member_no=member.member_no,
        full_name=member.full_name,
        email=member.email,
        phone=member.phone,
        membership_status=member.membership_status,
        joined_at=member.joined_at,
        has_login_account=False,
    )


@router.post(
    "/{member_id}/account",
    response_model=MemberAccountOut,
    status_code=201,
)
def create_member_account(
    member_id: str,
    payload: MemberAccountCreate,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_roles("admin")),
):
    member = db.get(Member, member_id)

    if not member:
        raise HTTPException(
            404,
            "Member not found",
        )

    if not member.email:
        raise HTTPException(
            400,
            "This member does not have an email address. Add an email before creating a login account.",
        )

    if member.user_id:
        raise HTTPException(
            409,
            "This member already has a login account.",
        )

    email = member.email.lower().strip()

    existing_user = db.scalar(
        select(User).where(User.email == email)
    )

    if existing_user:
        raise HTTPException(
            409,
            "A login account already exists for this email address.",
        )

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        role="member",
        is_active=True,

        # Security:
        # The password supplied by the administrator is temporary.
        # The member must replace it before accessing the platform.
        must_change_password=True,
    )

    db.add(user)
    db.flush()

    member.user_id = user.id

    write_audit(
        db,
        actor_user_id=admin_user.id,
        action="member_login_account_created",
        entity_type="member",
        entity_id=member.id,
        after={
            "member_id": member.id,
            "member_no": member.member_no,
            "user_id": user.id,
            "email": user.email,
            "role": user.role,
            "must_change_password": True,
        },
    )

    db.commit()

    db.refresh(member)
    db.refresh(user)

    return MemberAccountOut(
        status="ok",
        message="Login account created successfully. The member must change the temporary password before accessing the platform.",
        member_id=member.id,
        member_no=member.member_no,
        email=user.email,
        user_id=user.id,
        role=user.role,
    )
