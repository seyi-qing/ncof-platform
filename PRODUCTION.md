# NCOF Platform API — production runbook

## Required Vercel environment variables

Set these for **Production**:

- `APP_ENV=production`
- `DATABASE_URL` (provided by Neon)
- `SECRET_KEY` — random 32+ character secret
- `PAYMENT_WEBHOOK_SECRET` — random 32+ character secret
- `AUDIT_HASH_SECRET` — random 32+ character secret
- `CORS_ORIGINS` — comma-separated list containing the deployed NCOF web origin

Never commit real secrets or `.env` files.

## First database deployment

From the API project directory:

```bash
python scripts/migrate.py
python scripts/create_admin.py admin@example.com 'use-a-long-random-password'
```

Then:

1. Log in through `POST /api/v1/auth/login`.
2. Create the first member with `POST /api/v1/members`.
3. Link that member to a user account before enabling the member portal.
4. Verify `/ready` and `/api/v1/controls/audit/verify`.

## Production safety

- Payment webhooks require HMAC verification.
- Financial debit operations enforce available balance.
- Withdrawal/loan limits are enforced.
- Member users can only read their own financial data and dues.
- Refresh tokens are stored hashed and rotated.
- Audit-chain verification recomputes hashes.
- Do not expose database credentials in logs or screenshots.

## Election and voting controls

The production election module now supports:

- election positions and candidates
- scheduled opening/closing windows
- active-member eligibility
- one-member-one-vote enforcement with a database uniqueness constraint
- a participation record that stores voter identity separately from ballot content
- secret-ballot storage: ballot and selection tables contain no member ID
- one selection per position for the initial voting method
- validation that candidates belong to the selected election position
- no live vote totals while an election is open
- aggregate tally/results only after the election is closed
- participation reporting for administrators
- non-sensitive ballot receipt hashes

### Secret-ballot limitation

This is an application-level secret ballot. The ballot records deliberately do not contain a voter/member foreign key, but a database administrator with access to transaction timestamps and other operational records could potentially correlate activity. It should therefore not be represented as cryptographic-grade anonymity without an additional independent election infrastructure/security review.

### Election deployment order

1. Apply Alembic migration `0008_election_voting`.
2. Create an election.
3. Add positions.
4. Add candidates using position IDs.
5. Open the election.
6. Eligible active members retrieve their ballot and cast exactly one vote.
7. Close the election.
8. Read aggregate results.
