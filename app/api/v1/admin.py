from fastapi import APIRouter, Depends
from sqlalchemy import select, func, case
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User, Member, FinancialTransaction, Meeting, Attendance, MonthlyDues
from app.security import require_roles

router = APIRouter()

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
