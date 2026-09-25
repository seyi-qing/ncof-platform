from datetime import datetime, timezone
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import (User, Member, Notification, NotificationPreference, MonthlyDues,
                        FinancialTransaction, Account, Attendance, Meeting, WelfareClaim, LoanApplication,
                        LoanRepaymentSchedule)
from app.schemas import NotificationPreferenceUpdate, BroadcastNotificationIn
from app.security import current_user, require_roles

router = APIRouter()

def now(): return datetime.now(timezone.utc)

def member_for_user(db, user):
    member = db.scalar(select(Member).where(Member.user_id == user.id))
    if not member: raise HTTPException(404, "Member profile not linked to this account")
    return member

def preference(db, user):
    item = db.scalar(select(NotificationPreference).where(NotificationPreference.user_id == user.id))
    if not item:
        item = NotificationPreference(id=str(uuid4()), user_id=user.id)
        db.add(item); db.flush()
    return item

@router.get("/dashboard")
def member_dashboard(db: Session = Depends(get_db), user: User = Depends(current_user)):
    member = member_for_user(db, user)
    dues = db.scalar(select(func.coalesce(func.sum(MonthlyDues.amount_due - MonthlyDues.amount_paid), 0)).where(MonthlyDues.member_id == member.id)) or 0
    savings = db.scalar(select(func.coalesce(func.sum(FinancialTransaction.amount), 0)).join(Account, FinancialTransaction.account_id == Account.id).where(Account.member_id == member.id, Account.account_type == "savings", FinancialTransaction.status == "posted", FinancialTransaction.direction == "credit")) or 0
    savings_debit = db.scalar(select(func.coalesce(func.sum(FinancialTransaction.amount), 0)).join(Account, FinancialTransaction.account_id == Account.id).where(Account.member_id == member.id, Account.account_type == "savings", FinancialTransaction.status == "posted", FinancialTransaction.direction == "debit")) or 0
    outstanding_loan = db.scalar(select(func.coalesce(func.sum(LoanRepaymentSchedule.amount_due - LoanRepaymentSchedule.amount_paid), 0)).join(LoanApplication, LoanRepaymentSchedule.loan_id == LoanApplication.id).where(LoanApplication.member_id == member.id, LoanApplication.status == "disbursed")) or 0
    unread = db.scalar(select(func.count()).select_from(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None))) or 0
    attendance = db.scalar(select(func.count()).select_from(Attendance).where(Attendance.member_id == member.id)) or 0
    return {"member": {"id": member.id, "member_no": member.member_no, "full_name": member.full_name, "status": member.membership_status},
            "balances": {"dues_outstanding": str(dues), "savings": str(savings - savings_debit), "loan_outstanding": str(outstanding_loan)},
            "attendance_records": attendance, "unread_notifications": unread}

@router.get("/notifications")
def notifications(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return list(db.scalars(select(Notification).where(or_(Notification.user_id == user.id, Notification.member_id == select(Member.id).where(Member.user_id == user.id).scalar_subquery())).order_by(Notification.created_at.desc()).limit(100)).all())

@router.post("/notifications/{notification_id}/read")
def mark_read(notification_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    item = db.get(Notification, notification_id)
    if not item or (item.user_id != user.id): raise HTTPException(404, "Notification not found")
    item.read_at = item.read_at or now(); db.commit(); return {"status": "read", "id": item.id}

@router.get("/notification-preferences")
def get_preferences(db: Session = Depends(get_db), user: User = Depends(current_user)):
    item = preference(db, user); db.commit(); return item

@router.patch("/notification-preferences")
def update_preferences(payload: NotificationPreferenceUpdate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    item = preference(db, user)
    for field, value in payload.model_dump(exclude_none=True).items(): setattr(item, field, value)
    db.commit(); db.refresh(item); return item

@router.post("/notifications/broadcast", status_code=201)
def broadcast(payload: BroadcastNotificationIn, db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "executive", "secretary"))):
    members = list(db.scalars(select(Member).where(Member.membership_status == "active", Member.user_id.is_not(None))).all())
    rows = [Notification(id=str(uuid4()), member_id=m.id, user_id=m.user_id, title=payload.title, body=payload.body, notification_type=payload.notification_type, priority=payload.priority) for m in members]
    db.add_all(rows); db.commit(); return {"created": len(rows), "created_by": user.id}
