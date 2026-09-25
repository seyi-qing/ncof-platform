from datetime import date, timedelta
import hashlib
import hmac
import json
from decimal import Decimal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import (
    Account, FinancialTransaction, LedgerEntry, Member, User,
    WithdrawalRequest, LoanApplication, LoanRepaymentSchedule,
    WelfareClaim, Receipt, IdempotencyKey, PaymentWebhookEvent,
)
from app.schemas import (
    WithdrawalCreate, DecisionIn, LoanApplicationCreate, LoanRepaymentIn,
    WelfareClaimCreate, WebhookIn,
)
from app.security import current_user, require_roles
from app.core.config import settings

router = APIRouter()

STAFF = ("admin", "executive", "treasurer")
APPROVERS = ("admin", "executive", "treasurer")


def _member_or_404(db, member_id):
    member = db.get(Member, member_id)
    if not member:
        raise HTTPException(404, "Member not found")
    return member


def _account(db, member_id, account_type, lock=False):
    stmt = select(Account).where(Account.member_id == member_id, Account.account_type == account_type)
    if lock:
        stmt = stmt.with_for_update()
    account = db.scalar(stmt)
    if not account:
        account = Account(member_id=member_id, account_type=account_type)
        db.add(account)
        db.flush()
    return account


def _balance(db, member_id, account_type):
    account = db.scalar(select(Account).where(Account.member_id == member_id, Account.account_type == account_type))
    if not account:
        return Decimal("0")
    value = db.scalar(select(func.coalesce(func.sum(FinancialTransaction.amount), 0)).where(
        FinancialTransaction.account_id == account.id,
        FinancialTransaction.status == "posted",
        FinancialTransaction.direction == "credit",
    )) or Decimal("0")
    debits = db.scalar(select(func.coalesce(func.sum(FinancialTransaction.amount), 0)).where(
        FinancialTransaction.account_id == account.id,
        FinancialTransaction.status == "posted",
        FinancialTransaction.direction == "debit",
    )) or Decimal("0")
    return Decimal(value) - Decimal(debits)


def _post_tx(db, user, member_id, account_type, transaction_type, amount, direction, description):
    account = _account(db, member_id, account_type)
    reference = f"NCOF-TRX-{uuid4().hex[:16].upper()}"
    tx = FinancialTransaction(reference=reference, member_id=member_id, account_id=account.id,
                              transaction_type=transaction_type, amount=amount, direction=direction,
                              description=description, created_by=user.id, status="posted")
    db.add(tx); db.flush()
    if direction == "credit":
        entries = [
            LedgerEntry(transaction_id=tx.id, ledger_account=f"member:{member_id}:{account_type}", debit=0, credit=amount),
            LedgerEntry(transaction_id=tx.id, ledger_account=f"control:{account_type}", debit=amount, credit=0),
        ]
    else:
        entries = [
            LedgerEntry(transaction_id=tx.id, ledger_account=f"member:{member_id}:{account_type}", debit=amount, credit=0),
            LedgerEntry(transaction_id=tx.id, ledger_account=f"control:{account_type}", debit=0, credit=amount),
        ]
    db.add_all(entries)
    receipt = Receipt(transaction_id=tx.id, receipt_no=f"NCOF-RCP-{uuid4().hex[:12].upper()}")
    db.add(receipt)
    return tx


@router.post("/savings/withdrawals", status_code=201)
def request_withdrawal(payload: WithdrawalCreate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    member = _member_or_404(db, payload.member_id)
    if user.role == "member" and member.user_id != user.id:
        raise HTTPException(403, "You can only request your own withdrawal")
    if payload.amount > settings.withdrawal_max_amount:
        raise HTTPException(400, "Withdrawal exceeds configured maximum")
    balance = _balance(db, member.id, "savings")
    if payload.amount > balance:
        raise HTTPException(400, f"Insufficient savings balance. Available: {balance}")
    req = WithdrawalRequest(member_id=member.id, amount=payload.amount, reason=payload.reason, requested_by=user.id)
    db.add(req); db.commit(); db.refresh(req)
    return req


@router.get("/savings/withdrawals")
def list_withdrawals(db: Session = Depends(get_db), user: User = Depends(current_user)):
    if user.role == "member":
        member = db.scalar(select(Member).where(Member.user_id == user.id))
        if not member: return []
        return list(db.scalars(select(WithdrawalRequest).where(WithdrawalRequest.member_id == member.id).order_by(WithdrawalRequest.created_at.desc())).all())
    return list(db.scalars(select(WithdrawalRequest).order_by(WithdrawalRequest.created_at.desc())).all())


@router.post("/savings/withdrawals/{request_id}/decision")
def decide_withdrawal(request_id: str, payload: DecisionIn, db: Session = Depends(get_db), user: User = Depends(require_roles(*APPROVERS))):
    req = db.get(WithdrawalRequest, request_id)
    if not req: raise HTTPException(404, "Withdrawal request not found")
    if req.status != "pending": raise HTTPException(409, "Request already decided")
    if req.requested_by == user.id: raise HTTPException(403, "Maker/checker rule: requester cannot approve their own request")
    req.status = payload.decision
    req.decided_by = user.id
    req.decision_note = payload.note
    if payload.decision == "approved":
        if _balance(db, req.member_id, "savings") < req.amount: raise HTTPException(409, "Savings balance is no longer sufficient")
        _post_tx(db, user, req.member_id, "savings", "savings_withdrawal", req.amount, "debit", req.reason)
    db.commit(); return req


@router.post("/loans/applications", status_code=201)
def apply_loan(payload: LoanApplicationCreate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    member = _member_or_404(db, payload.member_id)
    if user.role == "member" and member.user_id != user.id: raise HTTPException(403, "You can only apply for yourself")
    if payload.amount > settings.loan_max_amount:
        raise HTTPException(400, "Loan amount exceeds configured maximum")
    active = db.scalar(select(LoanApplication).where(LoanApplication.member_id == member.id, LoanApplication.status.in_(["pending", "approved", "disbursed"])))
    if active: raise HTTPException(409, "Member already has an active loan application")
    app = LoanApplication(member_id=member.id, amount=payload.amount, term_months=payload.term_months, purpose=payload.purpose, requested_by=user.id)
    db.add(app); db.commit(); db.refresh(app); return app


@router.get("/loans/applications")
def list_loans(db: Session = Depends(get_db), user: User = Depends(current_user)):
    q = select(LoanApplication).order_by(LoanApplication.created_at.desc())
    if user.role == "member":
        member = db.scalar(select(Member).where(Member.user_id == user.id))
        q = q.where(LoanApplication.member_id == member.id) if member else q.where(False)
    return list(db.scalars(q).all())


@router.post("/loans/applications/{loan_id}/decision")
def decide_loan(loan_id: str, payload: DecisionIn, db: Session = Depends(get_db), user: User = Depends(require_roles(*APPROVERS))):
    loan = db.get(LoanApplication, loan_id)
    if not loan: raise HTTPException(404, "Loan application not found")
    if loan.status != "pending": raise HTTPException(409, "Loan is not pending")
    if loan.requested_by == user.id: raise HTTPException(403, "Maker/checker rule: requester cannot approve own loan")
    loan.status = payload.decision; loan.decided_by = user.id; loan.decision_note = payload.note
    if payload.decision == "approved":
        loan.approved_at = date.today()
    db.commit(); return loan


@router.post("/loans/applications/{loan_id}/disburse")
def disburse_loan(loan_id: str, db: Session = Depends(get_db), user: User = Depends(require_roles(*STAFF))):
    loan = db.get(LoanApplication, loan_id)
    if not loan: raise HTTPException(404, "Loan application not found")
    if loan.status != "approved": raise HTTPException(409, "Loan must be approved before disbursement")
    if loan.amount > settings.loan_max_amount:
        raise HTTPException(409, "Loan exceeds configured maximum")
    tx = _post_tx(db, user, loan.member_id, "loan", "loan_disbursement", loan.amount, "credit", loan.purpose)
    loan.status = "disbursed"; loan.disbursed_at = date.today(); loan.disbursed_transaction_id = tx.id
    monthly = (loan.amount / loan.term_months).quantize(Decimal("0.01"))
    total = Decimal("0")
    for i in range(1, loan.term_months + 1):
        due = monthly if i < loan.term_months else loan.amount - total
        total += due
        db.add(LoanRepaymentSchedule(loan_id=loan.id, installment_no=i, due_date=date.today() + timedelta(days=30*i), amount_due=due))
    db.commit(); return {"loan_id": loan.id, "transaction_reference": tx.reference}


@router.post("/loans/{loan_id}/repayments")
def repay_loan(loan_id: str, payload: LoanRepaymentIn, db: Session = Depends(get_db), user: User = Depends(require_roles(*STAFF))):
    loan = db.get(LoanApplication, loan_id)
    if not loan or loan.status != "disbursed": raise HTTPException(404, "Disbursed loan not found")
    outstanding = _balance(db, loan.member_id, "loan")
    if payload.amount > outstanding:
        raise HTTPException(400, f"Repayment exceeds outstanding loan balance of {outstanding}")
    tx = _post_tx(db, user, loan.member_id, "loan", "loan_repayment", payload.amount, "debit", payload.note)
    remaining = payload.amount
    rows = list(db.scalars(select(LoanRepaymentSchedule).where(LoanRepaymentSchedule.loan_id == loan.id, LoanRepaymentSchedule.status != "paid").order_by(LoanRepaymentSchedule.installment_no)).all())
    for row in rows:
        outstanding = row.amount_due - row.amount_paid
        applied = min(remaining, outstanding)
        row.amount_paid += applied
        row.status = "paid" if row.amount_paid >= row.amount_due else "partial"
        remaining -= applied
        if remaining <= 0: break
    db.commit(); return {"transaction_reference": tx.reference, "unallocated": str(remaining)}


@router.get("/loans/{loan_id}/schedule")
def loan_schedule(loan_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    loan = db.get(LoanApplication, loan_id)
    if not loan: raise HTTPException(404, "Loan not found")
    member = db.get(Member, loan.member_id)
    if user.role == "member" and member.user_id != user.id: raise HTTPException(403, "Forbidden")
    return list(db.scalars(select(LoanRepaymentSchedule).where(LoanRepaymentSchedule.loan_id == loan.id).order_by(LoanRepaymentSchedule.installment_no)).all())


@router.post("/welfare/claims", status_code=201)
def welfare_claim(payload: WelfareClaimCreate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    member = _member_or_404(db, payload.member_id)
    if user.role == "member" and member.user_id != user.id: raise HTTPException(403, "You can only submit your own claim")
    claim = WelfareClaim(member_id=member.id, amount=payload.amount, category=payload.category, reason=payload.reason, requested_by=user.id)
    db.add(claim); db.commit(); db.refresh(claim); return claim


@router.get("/welfare/claims")
def list_claims(db: Session = Depends(get_db), user: User = Depends(current_user)):
    q = select(WelfareClaim).order_by(WelfareClaim.created_at.desc())
    if user.role == "member":
        member = db.scalar(select(Member).where(Member.user_id == user.id)); q = q.where(WelfareClaim.member_id == member.id) if member else q.where(False)
    return list(db.scalars(q).all())


@router.post("/welfare/claims/{claim_id}/decision")
def decide_claim(claim_id: str, payload: DecisionIn, db: Session = Depends(get_db), user: User = Depends(require_roles(*APPROVERS))):
    claim = db.get(WelfareClaim, claim_id)
    if not claim: raise HTTPException(404, "Welfare claim not found")
    if claim.status != "pending": raise HTTPException(409, "Claim already decided")
    if claim.requested_by == user.id: raise HTTPException(403, "Maker/checker rule applies")
    claim.status = payload.decision; claim.decided_by = user.id; claim.decision_note = payload.note
    if payload.decision == "approved":
        if _balance(db, claim.member_id, "welfare") < claim.amount:
            raise HTTPException(409, "Insufficient welfare balance")
        tx = _post_tx(db, user, claim.member_id, "welfare", "welfare_claim", claim.amount, "debit", claim.reason)
        claim.disbursed_transaction_id = tx.id
    db.commit(); return claim


@router.get("/member/{member_id}/statement")
def statement(member_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    member = _member_or_404(db, member_id)
    if user.role == "member" and member.user_id != user.id: raise HTTPException(403, "Forbidden")
    txs = list(db.scalars(select(FinancialTransaction).where(FinancialTransaction.member_id == member_id, FinancialTransaction.status == "posted").order_by(FinancialTransaction.created_at)).all())
    balances = {t: str(_balance(db, member_id, t)) for t in ("dues", "savings", "welfare", "loan")}
    return {"member": {"id": member.id, "member_no": member.member_no, "name": member.full_name}, "balances": balances, "transactions": txs}


@router.get("/reports/financial-summary")
def financial_summary(db: Session = Depends(get_db), _: User = Depends(require_roles("admin", "executive", "treasurer", "auditor"))):
    result = {}
    for account_type in ("dues", "savings", "welfare", "loan"):
        credits = db.scalar(select(func.coalesce(func.sum(FinancialTransaction.amount), 0)).join(Account, FinancialTransaction.account_id == Account.id).where(Account.account_type == account_type, FinancialTransaction.status == "posted", FinancialTransaction.direction == "credit")) or 0
        debits = db.scalar(select(func.coalesce(func.sum(FinancialTransaction.amount), 0)).join(Account, FinancialTransaction.account_id == Account.id).where(Account.account_type == account_type, FinancialTransaction.status == "posted", FinancialTransaction.direction == "debit")) or 0
        result[account_type] = {"credits": str(credits), "debits": str(debits), "net": str(Decimal(credits)-Decimal(debits))}
    return result


@router.get("/receipts/{receipt_no}")
def get_receipt(receipt_no: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    receipt = db.scalar(select(Receipt).where(Receipt.receipt_no == receipt_no))
    if not receipt: raise HTTPException(404, "Receipt not found")
    tx = db.get(FinancialTransaction, receipt.transaction_id); member = db.get(Member, tx.member_id)
    if user.role == "member" and member.user_id != user.id: raise HTTPException(403, "Forbidden")
    return {"receipt_no": receipt.receipt_no, "issued_at": receipt.issued_at, "member": member.full_name, "member_no": member.member_no, "transaction": tx}


@router.post("/webhooks/payments")
async def payment_webhook(
    request: Request,
    x_webhook_signature: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    raw = await request.body()
    if not settings.payment_webhook_secret or settings.payment_webhook_secret.startswith("CHANGE_ME"):
        raise HTTPException(503, "Payment webhook is not configured")
    if not x_webhook_signature:
        raise HTTPException(401, "Missing webhook signature")
    expected = hmac.new(settings.payment_webhook_secret.encode(), raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, x_webhook_signature):
        raise HTTPException(401, "Invalid webhook signature")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(400, "Webhook body must be valid JSON")
    event_id = str(payload.get("event_id") or payload.get("id") or "")
    provider = str(payload.get("provider") or "unknown")
    if not event_id:
        raise HTTPException(400, "Webhook payload must contain event_id or id")
    existing = db.scalar(select(PaymentWebhookEvent).where(PaymentWebhookEvent.event_id == event_id))
    if existing:
        return {"status": "already_received", "event_id": event_id}
    event = PaymentWebhookEvent(
        event_id=event_id,
        provider=provider,
        payload_json=json.dumps(payload, sort_keys=True),
        signature=x_webhook_signature,
        verified=True,
        status="verified",
    )
    db.add(event)
    db.commit()
    return {"status": "verified", "event_id": event_id}
