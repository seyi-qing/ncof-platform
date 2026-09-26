from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import write_audit
from app.db import get_db
from app.models import Member, User
from app.schemas import (
    MemberCreate,
    MemberUpdate,
    MemberOut,
    MemberAccountCreate,
    MemberAccountOut,
    RoleUpdate,
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


@router.patch("/{member_id}", response_model=MemberOut)
def update_member(
    member_id: str,
    payload: MemberUpdate,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_roles("admin", "executive", "secretary")),
):
    """Update member registry fields (name, email, phone, status)."""
    member = db.get(Member, member_id)
    if not member:
        raise HTTPException(404, "Member not found")

    before = {
        "full_name": member.full_name,
        "email": member.email,
        "phone": member.phone,
        "membership_status": member.membership_status,
    }

    data = payload.model_dump(exclude_unset=True)
    if "full_name" in data and data["full_name"] is not None:
        member.full_name = data["full_name"].strip()
    if "email" in data:
        new_email = data["email"]
        if new_email is not None:
            new_email = str(new_email).lower().strip()
            if member.user_id:
                linked = db.get(User, member.user_id)
                if linked:
                    clash = db.scalar(
                        select(User).where(
                            User.email == new_email,
                            User.id != linked.id,
                        )
                    )
                    if clash:
                        raise HTTPException(409, "Another login already uses that email")
                    linked.email = new_email
        member.email = new_email
    if "phone" in data:
        member.phone = data["phone"]
    if "membership_status" in data and data["membership_status"] is not None:
        member.membership_status = data["membership_status"]
        # Tie login lockout to membership status:
        # suspended → cannot login; active → restore login; inactive leaves is_active unchanged
        if member.user_id:
            linked = db.get(User, member.user_id)
            if linked:
                if member.membership_status == "suspended":
                    linked.is_active = False
                elif member.membership_status == "active":
                    linked.is_active = True

    write_audit(
        db,
        actor_user_id=admin_user.id,
        action="member_updated",
        entity_type="member",
        entity_id=member.id,
        before=before,
        after={
            "full_name": member.full_name,
            "email": member.email,
            "phone": member.phone,
            "membership_status": member.membership_status,
        },
    )
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
        has_login_account=bool(member.user_id),
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

    assigned_role = (payload.role or "member").strip().lower()
    allowed_roles = {
        "member",
        "treasurer",
        "executive",
        "secretary",
        "auditor",
        "admin",
    }
    if assigned_role not in allowed_roles:
        raise HTTPException(400, f"Invalid role: {assigned_role}")

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        role=assigned_role,
        is_active=True,
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


@router.patch("/{member_id}/role")
def set_member_role(
    member_id: str,
    payload: RoleUpdate,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_roles("admin")),
):
    """Admin: change login role for a member who already has an account."""
    member = db.get(Member, member_id)
    if not member:
        raise HTTPException(404, "Member not found")
    if not member.user_id:
        raise HTTPException(400, "Member has no login account yet")
    user = db.get(User, member.user_id)
    if not user:
        raise HTTPException(404, "Linked user not found")

    role = payload.role.strip().lower()
    before = user.role
    user.role = role
    write_audit(
        db,
        actor_user_id=admin_user.id,
        action="member_role_changed",
        entity_type="user",
        entity_id=user.id,
        before={"role": before},
        after={"role": role, "member_id": member.id, "email": user.email},
    )
    db.commit()
    return {"status": "ok", "member_id": member.id, "email": user.email, "role": user.role}
