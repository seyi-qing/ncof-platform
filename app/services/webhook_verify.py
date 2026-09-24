"""Provider-specific payment webhook signature verification and payload normalization.

Supported providers:
  - paystack:     x-paystack-signature = HMAC-SHA512(raw_body, PAYSTACK_SECRET_KEY)
  - flutterwave:  verif-hash == FLW_SECRET_HASH  (classic)
                  or flutterwave-signature = HMAC-SHA256(raw_body) base64 (v4-style)
  - manual:       X-Webhook-Signature = HMAC-SHA256(canonical JSON, PAYMENT_WEBHOOK_SECRET)
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Any

from app.core.config import settings


class WebhookVerifyError(Exception):
    pass


def _compare(a: str, b: str) -> bool:
    if not a or not b:
        return False
    return hmac.compare_digest(a, b)


def verify_paystack(raw_body: bytes, signature: str | None) -> None:
    secret = (settings.paystack_secret_key or "").strip()
    if not secret or secret.startswith("CHANGE_ME"):
        raise WebhookVerifyError("PAYSTACK_SECRET_KEY is not configured")
    if not signature:
        raise WebhookVerifyError("Missing x-paystack-signature header")
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha512).hexdigest()
    if not _compare(expected, signature):
        raise WebhookVerifyError("Invalid Paystack signature")


def verify_flutterwave(
    raw_body: bytes,
    verif_hash: str | None,
    flutterwave_signature: str | None,
) -> None:
    secret = (settings.flw_secret_hash or "").strip()
    if not secret or secret.startswith("CHANGE_ME"):
        raise WebhookVerifyError("FLW_SECRET_HASH is not configured")

    # Classic: verif-hash equals the secret hash (most common)
    if verif_hash and _compare(verif_hash, secret):
        return

    # v4-style: HMAC-SHA256(raw body) as base64
    if flutterwave_signature:
        digest = hmac.new(secret.encode(), raw_body, hashlib.sha256).digest()
        expected_b64 = base64.b64encode(digest).decode()
        expected_hex = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
        if _compare(expected_b64, flutterwave_signature) or _compare(expected_hex, flutterwave_signature):
            return

    raise WebhookVerifyError("Invalid Flutterwave signature (verif-hash / flutterwave-signature)")


def verify_manual(raw_body: bytes, signature: str | None, payload: dict) -> None:
    secret = (settings.payment_webhook_secret or "").strip()
    if not secret or secret.startswith("CHANGE_ME"):
        raise WebhookVerifyError("PAYMENT_WEBHOOK_SECRET is not configured")
    if not signature:
        raise WebhookVerifyError("Missing X-Webhook-Signature header")
    # Prefer raw body when available; fall back to canonical JSON for typed dict callers
    if raw_body:
        expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
        if _compare(expected, signature):
            return
    canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    expected = hmac.new(secret.encode(), canonical, hashlib.sha256).hexdigest()
    if not _compare(expected, signature):
        raise WebhookVerifyError("Invalid manual webhook signature")


def verify_provider(
    provider: str,
    raw_body: bytes,
    payload: dict,
    *,
    x_webhook_signature: str | None = None,
    x_paystack_signature: str | None = None,
    verif_hash: str | None = None,
    flutterwave_signature: str | None = None,
) -> str:
    """Verify signature for provider. Returns the signature string stored for audit."""
    p = provider.lower().strip()
    if p == "paystack":
        verify_paystack(raw_body, x_paystack_signature)
        return x_paystack_signature or ""
    if p in {"flutterwave", "flw"}:
        verify_flutterwave(raw_body, verif_hash, flutterwave_signature)
        return verif_hash or flutterwave_signature or ""
    if p in {"manual", "generic", "test"}:
        verify_manual(raw_body, x_webhook_signature, payload)
        return x_webhook_signature or ""
    raise WebhookVerifyError(f"Unsupported provider: {provider}")


def extract_event_id(provider: str, payload: dict) -> str:
    p = provider.lower().strip()
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}

    if p == "paystack":
        for key in ("reference", "id"):
            if data.get(key) is not None:
                return f"paystack:{data[key]}"
        if payload.get("id") is not None:
            return f"paystack:{payload['id']}"
    if p in {"flutterwave", "flw"}:
        for key in ("flw_ref", "id", "tx_ref"):
            if data.get(key) is not None:
                return f"flw:{data[key]}"
        if payload.get("id") is not None:
            return f"flw:{payload['id']}"

    for key in ("event_id", "id", "reference"):
        if payload.get(key) is not None:
            return str(payload[key])
        if data.get(key) is not None:
            return str(data[key])
    raise WebhookVerifyError("Webhook payload must contain an event id / reference")


def normalize_for_settlement(provider: str, payload: dict) -> dict[str, Any]:
    """
    Map provider payload into the shape expected by payment_settlement:
      event_id, status, amount, currency, member_no|member_id, purpose/txn_type, reference
    """
    p = provider.lower().strip()
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    meta = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
    if not meta and isinstance(payload.get("metadata"), dict):
        meta = payload["metadata"]

    out: dict[str, Any] = dict(payload)

    if p == "paystack":
        event_name = str(payload.get("event") or "").lower()
        status = str(data.get("status") or "").lower()
        if event_name == "charge.success" or status in {"success", "successful"}:
            out["status"] = "success"
        else:
            out["status"] = status or event_name or "unknown"
        out["amount"] = data.get("amount")
        if out["amount"] is not None and str(data.get("currency") or "NGN").upper() == "NGN":
            try:
                amt = float(out["amount"])
                if amt >= 100 and float(out["amount"]) == int(amt):
                    out["amount"] = f"{amt / 100:.2f}"
            except (TypeError, ValueError):
                pass
        out["currency"] = data.get("currency") or "NGN"
        out["reference"] = data.get("reference")
        out["member_no"] = meta.get("member_no") or data.get("member_no")
        out["member_id"] = meta.get("member_id") or data.get("member_id")
        out["purpose"] = meta.get("purpose") or meta.get("txn_type") or "dues"
        out["event_id"] = extract_event_id(p, payload)
        return out

    if p in {"flutterwave", "flw"}:
        event_name = str(payload.get("event") or payload.get("type") or "").lower()
        status = str(data.get("status") or "").lower()
        if "completed" in event_name or status in {"successful", "success"}:
            out["status"] = "success"
        else:
            out["status"] = status or event_name or "unknown"
        out["amount"] = data.get("amount")
        out["currency"] = data.get("currency") or "NGN"
        out["reference"] = data.get("tx_ref") or data.get("flw_ref")
        customer = data.get("customer") if isinstance(data.get("customer"), dict) else {}
        out["member_no"] = meta.get("member_no") or data.get("member_no")
        out["member_id"] = meta.get("member_id") or data.get("member_id")
        if customer.get("email"):
            out.setdefault("metadata", {})
            if isinstance(out["metadata"], dict):
                out["metadata"]["customer_email"] = customer["email"]
        out["purpose"] = meta.get("purpose") or meta.get("txn_type") or "dues"
        out["event_id"] = extract_event_id(p, payload)
        return out

    out["event_id"] = extract_event_id(p, payload)
    if "status" not in out:
        out["status"] = "success"
    return out
