"""
Payment settlement adapter.

Current webhook flow (controls.py):
  POST /api/v1/controls/webhooks/{provider}
  -> HMAC signature check (PAYMENT_WEBHOOK_SECRET)
  -> store PaymentWebhookEvent (verified=True, status=verified)
  -> does NOT create FinancialTransaction yet

This module posts a verified event into the ledger:
  FinancialTransaction + LedgerEntry + Receipt

Idempotent on PaymentWebhookEvent.event_id via FinancialTransaction.reference.

Expected payload keys (provider-agnostic):
  event_id / id, status, amount, currency?, member_no? | member_id?,
  reference?, purpose? / txn_type? (dues|savings|loan_repayment|welfare|other)
"""
from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Member,
    Account,
    FinancialTransaction,
    LedgerEntry,
    Receipt,
    PaymentWebhookEvent,
)


class SettlementError(Exception):
    pass


def _parse_amount(value: Any) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise SettlementError(f"invalid amount: {value!r}") from exc
    if amount <= 0:
        raise SettlementError("amount must be positive")
    return amount.quantize(Decimal("0.01"))


def _payload(event: PaymentWebhookEvent) -> dict:
    try:
        data = json.loads(event.payload_json) if event.payload_json else {}
    except json.JSONDecodeError as exc:
        raise SettlementError("payload_json is not valid JSON") from exc
    if not isinstance(data, dict):
        raise SettlementError("payload must be a JSON object")
    return data


def _resolve_member(db: Session, payload: dict) -> Member:
    meta = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    member_id = payload.get("member_id") or meta.get("member_id")
    member_no = payload.get("member_no") or meta.get("member_no")
    if member_id:
        member = db.get(Member, str(member_id))
        if member:
            return member
    if member_no:
        member = db.scalar(select(Member).where(Member.member_no == str(member_no)))
        if member:
            return member
    raise SettlementError("member not found (need member_id or member_no)")


def _ensure_account(db: Session, member_id: str, account_type: str, currency: str) -> Account:
    account = db.scalar(
        select(Account).where(
            Account.member_id == member_id,
            Account.account_type == account_type,
        )
    )
    if account:
        return account
    account = Account(
        id=str(uuid4()),
        member_id=member_id,
        account_type=account_type,
        currency=currency,
        status="active",
    )
    db.add(account)
    db.flush()
    return account


def settle_webhook_event(db: Session, event: PaymentWebhookEvent) -> FinancialTransaction | None:
    """
    Post a verified webhook into the ledger.
    Returns FinancialTransaction if posted, None if not settleable (non-success status).
    Idempotent on event.event_id stored as FinancialTransaction.reference.
    """
    if not event.verified:
        raise SettlementError("event is not signature-verified")

    payload = _payload(event)
    status = str(payload.get("status") or event.status or "").lower()
    if status not in {"success", "successful", "completed", "verified"}:
        return None

    existing = db.scalar(
        select(FinancialTransaction).where(FinancialTransaction.reference == event.event_id)
    )
    if existing:
        return existing

    amount = _parse_amount(payload.get("amount") or payload.get("amount_paid"))
    member = _resolve_member(db, payload)
    currency = str(payload.get("currency") or "NGN").upper()[:3]
    txn_type = str(payload.get("txn_type") or payload.get("purpose") or "dues").lower()
    if txn_type not in {"dues", "savings", "loan_repayment", "welfare", "other"}:
        txn_type = "other"

    account_type = {
        "dues": "dues",
        "savings": "savings",
        "loan_repayment": "loan",
        "welfare": "welfare",
        "other": "general",
    }.get(txn_type, "general")
    account = _ensure_account(db, member.id, account_type, currency)

    now = datetime.now(timezone.utc)
    txn = FinancialTransaction(
        id=str(uuid4()),
        reference=event.event_id,
        member_id=member.id,
        account_id=account.id,
        transaction_type=txn_type,
        amount=amount,
        direction="credit",
        description=f"Webhook {event.provider}: {payload.get('reference') or event.event_id}",
        status="posted",
        created_at=now,
    )
    db.add(txn)
    db.flush()

    db.add(
        LedgerEntry(
            id=str(uuid4()),
            transaction_id=txn.id,
            ledger_account=f"member.{account_type}",
            debit=Decimal("0.00"),
            credit=amount,
            created_at=now,
        )
    )
    db.add(
        LedgerEntry(
            id=str(uuid4()),
            transaction_id=txn.id,
            ledger_account="cash.clearing",
            debit=amount,
            credit=Decimal("0.00"),
            created_at=now,
        )
    )

    receipt_no = f"RCPT-{now.strftime('%Y%m%d')}-{txn.id[:8].upper()}"
    db.add(
        Receipt(
            id=str(uuid4()),
            transaction_id=txn.id,
            receipt_no=receipt_no,
            issued_at=now,
        )
    )

    event.processed_at = now
    event.status = "settled"
    db.flush()
    return txn


def settle_pending_events(db: Session, limit: int = 50) -> list[str]:
    """Settle verified, unprocessed webhook events. Returns transaction ids posted."""
    rows = db.scalars(
        select(PaymentWebhookEvent)
        .where(PaymentWebhookEvent.verified.is_(True))
        .where(PaymentWebhookEvent.processed_at.is_(None))
        .order_by(PaymentWebhookEvent.created_at.asc())
        .limit(limit)
    ).all()
    posted: list[str] = []
    for event in rows:
        try:
            txn = settle_webhook_event(db, event)
            if txn:
                posted.append(txn.id)
        except SettlementError:
            continue
    if posted:
        db.commit()
    return posted
