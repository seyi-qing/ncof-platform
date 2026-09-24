# NCOF Platform API v1.7.0 — Production Release

## Included
- PostgreSQL/Neon production configuration with Psycopg 3 URL normalization.
- Production secret validation and distinct application/webhook/audit secrets.
- Deterministic Alembic migration chain through `0008_election_voting`.
- Financial controls, webhook verification/idempotency, refresh-token rotation, audit-chain verification.
- Provider-specific webhooks: Paystack (HMAC-SHA512), Flutterwave (verif-hash), manual (HMAC-SHA256).
- Payment settlement adapter (webhook event → FinancialTransaction + LedgerEntry + Receipt).
- Real election workflow with application-level secret ballot.
- GitHub Actions CI.

## Privacy note
The voting implementation is an application-level secret ballot. Ballot records do not contain a member ID. This is not cryptographic anonymity.

## Validation
- Python compilation: passed.
- Focused automated tests: schema/config focused.
- Alembic revision-chain: `0001` → `0007` merge → `0008_election_voting`.
