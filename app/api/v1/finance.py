from decimal import Decimal
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Account, FinancialTransaction, LedgerEntry, Member, MonthlyDues, User, Receipt
from app.schemas import DuesGenerationIn, TransactionIn
from app.security import require_roles, current_user

router = APIRouter()

@router.post("/dues/generate", status_code=201)
def generate_monthly_dues(
    payload: DuesGenerationIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "executive", "treasurer")),
):
    members = list(db.scalars(select(Member).where(Member.membership_status == "active")).all())
    created = 0
    for member in members:
        existing = db.scalar(select(MonthlyDues).where(
            MonthlyDues.member_id == member.id,
            MonthlyDues.year == payload.year,
            MonthlyDues.month == payload.month,
        ))
        if not existing:
            db.add(MonthlyDues(
                id=str(uuid4()),
                member_id=member.id,
                year=payload.year,
                month=payload.month,
                amount_due=payload.amount,
                amount_paid=Decimal("0"),
                status="unpaid",
            ))
            created += 1
    db.commit()
    return {"created": created, "year": payload.year, "month": payload.month}

@router.get("/dues")
def dues(
    year: int,
    month: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "executive", "treasurer", "secretary", "auditor", "member")),
):
    q = select(MonthlyDues).where(MonthlyDues.year == year, MonthlyDues.month == month)
    if user.role == "member":
        member = db.scalar(select(Member).where(Member.user_id == user.id))
        q = q.where(MonthlyDues.member_id == member.id) if member else q.where(False)
    rows = list(db.scalars(q.order_by(MonthlyDues.status, MonthlyDues.member_id)).all())
    out = []
    for r in rows:
        m = db.get(Member, r.member_id)
        out.append({
            "id": r.id,
            "member_id": r.member_id,
            "member_name": m.full_name if m else None,
            "member_no": m.member_no if m else None,
            "year": r.year,
            "month": r.month,
            "amount_due": r.amount_due,
            "amount_paid": r.amount_paid,
            "status": r.status,
        })
    return out

@router.post("/transactions", status_code=201)
def post_transaction(
    payload: TransactionIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "executive", "treasurer")),
):
    member = db.get(Member, payload.member_id)
    if not member:
        raise HTTPException(404, "Member not found")

    if payload.account_type == "dues" and payload.direction == "credit":
        outstanding_dues = db.scalar(
            select(func.coalesce(func.sum(MonthlyDues.amount_due - MonthlyDues.amount_paid), 0))
            .where(MonthlyDues.member_id == member.id, MonthlyDues.status != "paid")
        ) or 0
        if outstanding_dues <= 0:
            raise HTTPException(400, "Member has no outstanding dues to pay")
        if payload.amount > Decimal(outstanding_dues):
            raise HTTPException(400, f"Dues payment exceeds outstanding balance of {outstanding_dues}")

    account = db.scalar(select(Account).where(Account.member_id == member.id, Account.account_type == payload.account_type))
    if not account:
        account = Account(id=str(uuid4()), member_id=member.id, account_type=payload.account_type, balance=Decimal("0"))
        db.add(account)
        db.flush()

    if payload.direction == "credit":
        account.balance = (account.balance or Decimal("0")) + payload.amount
    else:
        if (account.balance or Decimal("0")) < payload.amount:
            raise HTTPException(400, "Insufficient balance")
        account.balance = account.balance - payload.amount

    ref = f"TX-{uuid4().hex[:10].upper()}"
    tx = FinancialTransaction(
        id=str(uuid4()),
        member_id=member.id,
        account_id=account.id,
        account_type=payload.account_type,
        transaction_type=payload.transaction_type,
        amount=payload.amount,
        direction=payload.direction,
        description=payload.description,
        reference=ref,
        posted_by=user.id,
    )
    db.add(tx)
    db.add(LedgerEntry(
        id=str(uuid4()),
        transaction_id=tx.id,
        account_id=account.id,
        amount=payload.amount if payload.direction == "credit" else -payload.amount,
        balance_after=account.balance,
    ))
    db.add(Receipt(id=str(uuid4()), transaction_id=tx.id, receipt_no=f"R-{uuid4().hex[:8].upper()}", issued_by=user.id))

    if payload.account_type == "dues":
        remaining = payload.amount
        dues_rows = list(db.scalars(select(MonthlyDues).where(
            MonthlyDues.member_id == member.id,
            MonthlyDues.status != "paid"
        ).order_by(MonthlyDues.year, MonthlyDues.month)).all())
        for row in dues_rows:
            if remaining <= 0:
                break
            outstanding = row.amount_due - row.amount_paid
            pay = min(remaining, outstanding)
            row.amount_paid = row.amount_paid + pay
            remaining -= pay
            row.status = "paid" if row.amount_paid >= row.amount_due else "partial"

    db.commit()
    db.refresh(tx)
    return {"id": tx.id, "reference": ref, "status": "posted"}
