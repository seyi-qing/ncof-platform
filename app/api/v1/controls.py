import json
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.audit import verify_audit_chain, write_audit
from app.db import get_db
from app.models import AuditLog, FinancialTransaction, PaymentWebhookEvent, User
from app.security import require_roles

router = APIRouter()
STAFF = ("admin", "executive", "treasurer")
AUDITORS = ("admin", "executive", "treasurer", "auditor")


def audit(
    db,
    user,
    action,
    entity_type,
    entity_id,
    before=None,
    after=None,
):
    """Compatibility wrapper using the canonical audit implementation."""
    return write_audit(
        db,
        actor_user_id=user.id if user else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before=before,
        after=after,
    )


@router.post("/transactions/{transaction_id}/reverse")
def reverse_transaction(
    transaction_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*STAFF)),
):
    txn = db.get(FinancialTransaction, transaction_id)
    if not txn or txn.status != "posted":
        raise HTTPException(404, "Posted transaction not found")
    if txn.reversed_by_transaction_id:
        raise HTTPException(400, "Already reversed")

    txn.status = "reversed"
    audit(
        db,
        user,
        "reverse_transaction",
        "financial_transactions",
        transaction_id,
        after={"status": "reversed"},
    )
    db.commit()
    return {"status": "reversed", "transaction_id": transaction_id}


@router.get("/audit/verify")
def verify_audit_chain_endpoint(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*AUDITORS)),
):
    return verify_audit_chain(db)


@router.post("/webhooks/{provider}")
async def verified_webhook(
    provider: str,
    request: Request,
    db: Session = Depends(get_db),
    x_webhook_signature: str | None = Header(default=None),
    x_paystack_signature: str | None = Header(
        default=None,
        alias="x-paystack-signature",
    ),
    verif_hash: str | None = Header(
        default=None,
        alias="verif-hash",
    ),
    flutterwave_signature: str | None = Header(
        default=None,
        alias="flutterwave-signature",
    ),
):
    """Ingest provider webhooks with provider-specific signature verification.

    Providers:
      - paystack:     header x-paystack-signature (HMAC-SHA512 of raw body)
      - flutterwave:  header verif-hash (equals FLW_SECRET_HASH) or flutterwave-signature
      - manual:       header X-Webhook-Signature (HMAC-SHA256)

    Always returns 200 on success so providers stop retrying. Settlement is separate
    (POST .../settle/{event_id} or settle-pending).
    """
    from app.services.webhook_verify import (
        WebhookVerifyError,
        extract_event_id,
        normalize_for_settlement,
        verify_provider,
    )

    raw_body = await request.body()
    try:
        payload = json.loads(raw_body.decode() or "{}")
    except json.JSONDecodeError:
        raise HTTPException(400, "Webhook body must be valid JSON")
    if not isinstance(payload, dict):
        raise HTTPException(400, "Webhook body must be a JSON object")

    try:
        stored_sig = verify_provider(
            provider,
            raw_body,
            payload,
            x_webhook_signature=x_webhook_signature,
            x_paystack_signature=x_paystack_signature,
            verif_hash=verif_hash,
            flutterwave_signature=flutterwave_signature,
        )
        event_id = extract_event_id(provider, payload)
    except WebhookVerifyError as exc:
        raise HTTPException(401, str(exc)) from exc

    existing = db.scalar(
        select(PaymentWebhookEvent).where(
            PaymentWebhookEvent.event_id == event_id
        )
    )
    if existing:
        return {
            "status": "already_processed",
            "event_id": event_id,
            "provider": provider.lower(),
        }

    normalized = normalize_for_settlement(provider, payload)
    normalized["event_id"] = event_id
    event = PaymentWebhookEvent(
        event_id=event_id,
        provider=provider.lower().strip(),
        payload_json=json.dumps(
            normalized,
            sort_keys=True,
            default=str,
        ),
        signature=stored_sig[:255] if stored_sig else None,
        verified=True,
        status="verified",
    )
    db.add(event)
    db.commit()
    return {
        "status": "verified",
        "event_id": event_id,
        "provider": provider.lower(),
    }


@router.get("/controls/health")
def controls_health(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*AUDITORS)),
):
    return {
        "audit_entries": db.scalar(
            select(func.count(AuditLog.id))
        )
        or 0,
        "posted_transactions": db.scalar(
            select(func.count(FinancialTransaction.id)).where(
                FinancialTransaction.status == "posted"
            )
        )
        or 0,
        "verified_webhooks": db.scalar(
            select(func.count(PaymentWebhookEvent.id)).where(
                PaymentWebhookEvent.verified.is_(True)
            )
        )
        or 0,
    }


@router.post("/webhooks/{provider}/settle/{event_id}")
def settle_webhook(
    provider: str,
    event_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "treasurer")),
):
    """Manually settle a verified webhook event into the ledger."""
    from app.services.payment_settlement import (
        SettlementError,
        settle_webhook_event,
    )

    event = db.scalar(
        select(PaymentWebhookEvent).where(
            PaymentWebhookEvent.event_id == event_id,
            PaymentWebhookEvent.provider == provider,
        )
    )
    if not event:
        raise HTTPException(404, "Webhook event not found")

    try:
        txn = settle_webhook_event(db, event)
        db.commit()
    except SettlementError as exc:
        raise HTTPException(400, str(exc)) from exc

    if not txn:
        return {
            "status": "skipped",
            "reason": "non-success status",
        }

    return {
        "status": "settled",
        "transaction_id": txn.id,
        "reference": txn.reference,
    }


@router.post("/webhooks/settle-pending")
def settle_pending(
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "treasurer")),
):
    """Batch-settle verified webhooks that have not been posted yet."""
    from app.services.payment_settlement import settle_pending_events

    ids = settle_pending_events(
        db,
        limit=min(limit, 200),
    )
    return {
        "settled_count": len(ids),
        "transaction_ids": ids,
    }
