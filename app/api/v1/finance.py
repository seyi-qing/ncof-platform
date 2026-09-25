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
    _: User = Depends(require_roles("admin", "executive", "treasurer")),
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
                member_id=member.id,
                year=payload.year,
                month=payload.month,
                amount_due=payload.amount,
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
    return list(db.scalars(q.order_by(MonthlyDues.status, MonthlyDues.member_id)).all())

@router.post("/transactions", status_code=201)
def post_transaction(
    payload: TransactionIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "executive", "treasurer")),
):
    member = db.get(Member, payload.member_id)
    if not member:
        raise HTTPException(404, "Member not found")

    account = db.scalar(
        select(Account)
        .where(Account.member_id == member.id, Account.account_type == payload.account_type)
        .with_for_update()
    )
    if not account:
        account = Account(member_id=member.id, account_type=payload.account_type)
        db.add(account)
        db.flush()

    if payload.account_type == "dues" and payload.direction == "credit":
        outstanding_dues = db.scalar(
            select(func.coalesce(func.sum(MonthlyDues.amount_due - MonthlyDues.amount_paid), 0))
            .where(MonthlyDues.member_id == member.id, MonthlyDues.status != "paid")
        ) or Decimal("0")
        if outstanding_dues <= 0:
            raise HTTPException(400, "Member has no outstanding dues to pay")
        if payload.amount > Decimal(outstanding_dues):
            raise HTTPException(400, f"Dues payment exceeds outstanding balance of {outstanding_dues}")

    if payload.direction == "debit":
        credits = db.scalar(select(func.coalesce(func.sum(FinancialTransaction.amount), 0)).where(
            FinancialTransaction.account_id == account.id, FinancialTransaction.status == "posted",
            FinancialTransaction.direction == "credit"
        )) or Decimal("0")
        debits = db.scalar(select(func.coalesce(func.sum(FinancialTransaction.amount), 0)).where(
            FinancialTransaction.account_id == account.id, FinancialTransaction.status == "posted",
            FinancialTransaction.direction == "debit"
        )) or Decimal("0")
        if payload.amount > Decimal(credits) - Decimal(debits):
            raise HTTPException(400, "Insufficient account balance")

    reference = f"NCOF-TRX-{uuid4().hex[:16].upper()}"
    tx = FinancialTransaction(
        reference=reference,
        member_id=member.id,
        account_id=account.id,
        transaction_type=payload.transaction_type,
        amount=payload.amount,
        direction=payload.direction,
        description=payload.description,
        created_by=user.id,
    )
    db.add(tx)
    db.flush()

    if payload.direction == "credit":
        entries = [
            LedgerEntry(transaction_id=tx.id, ledger_account=f"member:{member.id}:{payload.account_type}", debit=0, credit=payload.amount),
            LedgerEntry(transaction_id=tx.id, ledger_account=f"control:{payload.account_type}", debit=payload.amount, credit=0),
        ]
    else:
        entries = [
            LedgerEntry(transaction_id=tx.id, ledger_account=f"member:{member.id}:{payload.account_type}", debit=payload.amount, credit=0),
            LedgerEntry(transaction_id=tx.id, ledger_account=f"control:{payload.account_type}", debit=0, credit=payload.amount),
        ]
    db.add_all(entries)
    db.add(Receipt(transaction_id=tx.id, receipt_no=f"NCOF-RCP-{uuid4().hex[:12].upper()}"))

    if payload.account_type == "dues":
        remaining = payload.amount
        dues_rows = list(db.scalars(select(MonthlyDues).where(
            MonthlyDues.member_id == member.id,
            MonthlyDues.status != "paid"
        ).order_by(MonthlyDues.year, MonthlyDues.month)).all())
        for row in dues_rows:
            outstanding = row.amount_due - row.amount_paid
            applied = min(remaining, outstanding)
            if applied > 0:
                row.amount_paid += applied
                row.status = "paid" if row.amount_paid >= row.amount_due else "partial"
                remaining -= applied
            if remaining <= 0:
                break

    db.commit()
    return {"reference": reference, "status": "posted", "amount": str(payload.amount)}

@router.get("/member/{member_id}/transactions")
def member_transactions(
    member_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    member = db.get(Member, member_id)
    if not member:
        raise HTTPException(404, "Member not found")
    if user.role == "member" and member.user_id != user.id:
        raise HTTPException(403, "You can only view your own transactions")
    return list(db.scalars(select(FinancialTransaction).where(
        FinancialTransaction.member_id == member_id
    ).order_by(FinancialTransaction.created_at.desc())).all())

@router.get("/member/{member_id}/summary")
def member_summary(
    member_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    member = db.get(Member, member_id)
    if not member:
        raise HTTPException(404, "Member not found")
    if user.role == "member" and member.user_id != user.id:
        raise HTTPException(403, "You can only view your own summary")

    rows = list(db.execute(
        select(FinancialTransaction.account_id, FinancialTransaction.direction, func.sum(FinancialTransaction.amount))
        .where(FinancialTransaction.member_id == member_id, FinancialTransaction.status == "posted")
        .group_by(FinancialTransaction.account_id, FinancialTransaction.direction)
    ).all())
    return [{"account_id": r[0], "direction": r[1], "total": str(r[2])} for r in rows]
