from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, func, text
from sqlalchemy.orm import Session

from app.db import get_db, engine
from app.models import User, Member, FinancialTransaction, Meeting, Attendance, MonthlyDues
from app.security import require_roles, hash_password
from app.core.config import settings

router = APIRouter()


class BootstrapIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


def _repo_root():
    from pathlib import Path
    here = Path(__file__).resolve()
    candidates = [
        here.parents[3],
        here.parents[2],
        Path.cwd(),
        Path("/var/task"),
    ]
    for root in candidates:
        if (root / "alembic.ini").exists() and (root / "alembic" / "versions").exists():
            return root
    return here.parents[3]


def _prepare_alembic_version_column():
    """Widen alembic_version.version_num if the table already exists (legacy default is VARCHAR(32))."""
    with engine.begin() as conn:
        exists = conn.execute(text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = 'alembic_version'"
        )).scalar()
        if exists:
            conn.execute(text(
                "ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(64)"
            ))


@router.post("/bootstrap", status_code=201)
def bootstrap(
    payload: BootstrapIn,
    db: Session = Depends(get_db),
    x_bootstrap_key: str | None = Header(default=None, alias="X-Bootstrap-Key"),
):
    """
    One-time production bootstrap (phone-friendly).

    1. Runs Alembic migrations to head (creates all tables).
    2. Creates the first admin user.

    Requires header: X-Bootstrap-Key: <same value as SECRET_KEY>
    Refuses if any user already exists.
    """
    if not x_bootstrap_key or x_bootstrap_key != settings.secret_key:
        raise HTTPException(401, "Invalid or missing X-Bootstrap-Key")

    try:
        _prepare_alembic_version_column()
    except Exception:
        pass

    try:
        from alembic.config import Config
        from alembic import command

        root = _repo_root()
        cfg = Config(str(root / "alembic.ini"))
        cfg.set_main_option("sqlalchemy.url", settings.database_url)
        cfg.set_main_option("script_location", str(root / "alembic"))
        command.upgrade(cfg, "head")
    except Exception as exc:
        raise HTTPException(500, f"Migration failed: {type(exc).__name__}: {exc}") from exc

    try:
        existing = db.scalar(select(func.count()).select_from(User)) or 0
    except Exception as exc:
        raise HTTPException(500, f"Schema still missing after migrate: {exc}") from exc

    if existing > 0:
        raise HTTPException(409, "Users already exist — bootstrap is one-time only")

    email = payload.email.lower().strip()
    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        role="admin",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {
        "status": "ok",
        "message": "Migrations applied and admin created",
        "admin_email": user.email,
        "admin_id": user.id,
        "next": "POST /api/v1/auth/login with this email and password",
    }


@router.post("/migrate")
def migrate(
    x_bootstrap_key: str | None = Header(default=None, alias="X-Bootstrap-Key"),
):
    """
    Apply pending Alembic migrations to head (phone-friendly).

    Does NOT create users. Safe to call repeatedly.
    Requires header: X-Bootstrap-Key: <same value as SECRET_KEY>
    """
    if not x_bootstrap_key or x_bootstrap_key != settings.secret_key:
        raise HTTPException(401, "Invalid or missing X-Bootstrap-Key")

    try:
        _prepare_alembic_version_column()
    except Exception:
        pass

    try:
        from alembic.config import Config
        from alembic import command
        from alembic.runtime.migration import MigrationContext

        root = _repo_root()
        cfg = Config(str(root / "alembic.ini"))
        cfg.set_main_option("sqlalchemy.url", settings.database_url)
        cfg.set_main_option("script_location", str(root / "alembic"))

        before = None
        with engine.connect() as conn:
            ctx = MigrationContext.configure(conn)
            before = ctx.get_current_revision()

        command.upgrade(cfg, "head")

        after = None
        with engine.connect() as conn:
            ctx = MigrationContext.configure(conn)
            after = ctx.get_current_revision()

        # Ensure critical column exists even if stamp was inconsistent
        with engine.begin() as conn:
            conn.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS "
                "must_change_password BOOLEAN NOT NULL DEFAULT false"
            ))

        return {
            "status": "ok",
            "message": "Migrations applied",
            "revision_before": before,
            "revision_after": after,
            "head": "0009_password_security",
            "next": "POST /api/v1/auth/login",
        }
    except Exception as exc:
        raise HTTPException(500, f"Migration failed: {type(exc).__name__}: {exc}") from exc


@router.get("/dashboard")
def dashboard(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "executive", "treasurer", "secretary", "auditor")),
):
    dues_due = db.scalar(select(func.coalesce(func.sum(MonthlyDues.amount_due), 0)))
    dues_paid = db.scalar(select(func.coalesce(func.sum(MonthlyDues.amount_paid), 0)))
    savings_credit = db.scalar(select(func.coalesce(func.sum(FinancialTransaction.amount), 0)).where(
        FinancialTransaction.transaction_type == "savings_deposit",
        FinancialTransaction.direction == "credit",
        FinancialTransaction.status == "posted",
    ))
    return {
        "members": db.scalar(select(func.count()).select_from(Member)) or 0,
        "users": db.scalar(select(func.count()).select_from(User)) or 0,
        "meetings": db.scalar(select(func.count()).select_from(Meeting)) or 0,
        "transactions": db.scalar(select(func.count()).select_from(FinancialTransaction)) or 0,
        "dues_due": str(dues_due or 0),
        "dues_paid": str(dues_paid or 0),
        "savings_deposits": str(savings_credit or 0),
    }
