from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User, LoginAttempt
from app.schemas import (
    LoginIn,
    TokenOut,
    RefreshIn,
    ChangePasswordIn,
)
from app.security import (
    verify_password,
    hash_password,
    create_access_token,
    issue_refresh_token,
    rotate_refresh_token,
    current_user_allow_password_change,
)
from app.core.config import settings

router = APIRouter()


def _attempt(db, email, ip):
    row = db.scalar(
        select(LoginAttempt).where(
            LoginAttempt.email == email,
            LoginAttempt.ip_address == ip,
        )
    )

    if not row:
        row = LoginAttempt(
            email=email,
            ip_address=ip,
            failed_count=0,
        )
        db.add(row)
        db.flush()

    return row


@router.post("/login", response_model=TokenOut)
def login(
    payload: LoginIn,
    request: Request,
    db: Session = Depends(get_db),
):
    email = payload.email.lower().strip()
    ip = request.client.host if request.client else "unknown"

    attempt = _attempt(db, email, ip)
    now = datetime.now(timezone.utc)

    if attempt.locked_until and attempt.locked_until > now:
        raise HTTPException(
            429,
            "Too many failed login attempts. Try again later.",
        )

    user = db.scalar(
        select(User).where(User.email == email)
    )

    if not user or not verify_password(
        payload.password,
        user.password_hash,
    ):
        attempt.failed_count += 1
        attempt.last_failed_at = now

        if attempt.failed_count >= settings.login_max_attempts:
            attempt.locked_until = now + timedelta(
                minutes=settings.login_lockout_minutes
            )

        db.commit()

        raise HTTPException(
            401,
            "Invalid credentials",
        )

    attempt.failed_count = 0
    attempt.locked_until = None
    attempt.last_failed_at = None

    refresh, _ = issue_refresh_token(
        db,
        user.id,
    )

    db.commit()

    return TokenOut(
        access_token=create_access_token(
            user.id,
            user.role,
        ),
        refresh_token=refresh,
        must_change_password=user.must_change_password,
    )


@router.post("/refresh", response_model=TokenOut)
def refresh(
    payload: RefreshIn,
    db: Session = Depends(get_db),
):
    result = rotate_refresh_token(
        db,
        payload.refresh_token,
    )

    if not result:
        raise HTTPException(
            401,
            "Invalid or expired refresh token",
        )

    raw, row = result
    user = db.get(User, row.user_id)

    if not user or not user.is_active:
        db.rollback()

        raise HTTPException(
            401,
            "Inactive user",
        )

    db.commit()

    return TokenOut(
        access_token=create_access_token(
            user.id,
            user.role,
        ),
        refresh_token=raw,
        must_change_password=user.must_change_password,
    )


@router.post("/change-password", response_model=TokenOut)
def change_password(
    payload: ChangePasswordIn,
    user: User = Depends(
        current_user_allow_password_change
    ),
    db: Session = Depends(get_db),
):
    if not verify_password(
        payload.current_password,
        user.password_hash,
    ):
        raise HTTPException(
            400,
            "Current password is incorrect.",
        )

    if verify_password(
        payload.new_password,
        user.password_hash,
    ):
        raise HTTPException(
            400,
            "New password must be different from the current password.",
        )

    user.password_hash = hash_password(
        payload.new_password
    )

    user.must_change_password = False

    refresh, _ = issue_refresh_token(
        db,
        user.id,
    )

    db.commit()

    return TokenOut(
        access_token=create_access_token(
            user.id,
            user.role,
        ),
        refresh_token=refresh,
        must_change_password=False,
        )
