# NCOF Platform API 1.7.0

Production-oriented FastAPI backend for the Nigerian Committee of Friends association platform.

## Stack

- FastAPI
- SQLAlchemy 2
- PostgreSQL / Neon
- Psycopg 3
- Alembic
- JWT access tokens + hashed rotating refresh tokens
- Vercel Python runtime

## Production deployment

1. Connect Neon and expose `DATABASE_URL` to Production.
2. Set `APP_ENV=production`.
3. Set strong `SECRET_KEY`, `PAYMENT_WEBHOOK_SECRET`, and `AUDIT_HASH_SECRET`.
4. Set `CORS_ORIGINS` to the deployed web application origin.
5. Optionally set `PAYSTACK_SECRET_KEY` and `FLW_SECRET_HASH` for payment webhooks.
6. Run `python scripts/migrate.py` against the production database.
7. Create the first administrator with `python scripts/create_admin.py EMAIL PASSWORD`.
8. Verify `/health`, `/ready`, `/docs`, and `/api/v1/controls/audit/verify`.

## Webhooks

- Paystack: `POST /api/v1/controls/webhooks/paystack` (header `x-paystack-signature`)
- Flutterwave: `POST /api/v1/controls/webhooks/flutterwave` (header `verif-hash`)
- Manual: `POST /api/v1/controls/webhooks/manual` (header `X-Webhook-Signature`)
- Settle: `POST /api/v1/controls/webhooks/{provider}/settle/{event_id}`

## Important

The migration chain is deterministic for a fresh database.
Payment webhooks are signature-verified before being recorded. Settle them into the ledger via the settle endpoints.
The election module manages election records, candidates, and open/close state with an application-level secret ballot.
