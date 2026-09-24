# NCOF Platform API — Production Deploy Guide (Vercel + Neon + GitHub)

This is the backend-only API (v1.7.0). Frontend is separate.

## Architecture (what each folder does)

| Path | Role |
|------|------|
| `api/index.py` | Vercel serverless entry: `from app.main import app` |
| `app/main.py` | FastAPI app, CORS, `/health`, `/ready` |
| `app/core/config.py` | Env settings + production secret validation |
| `app/db.py` | SQLAlchemy engine (pool_size=1 for serverless) |
| `app/models.py` | All ORM tables (members, finance, elections, …) |
| `app/schemas.py` | Pydantic request/response models |
| `app/security.py` | bcrypt, JWT access, hashed rotating refresh tokens, RBAC |
| `app/api/v1/*.py` | Route modules mounted under `/api/v1` |
| `alembic/versions/` | Ordered migrations through `0008_election_voting` |
| `scripts/migrate.py` | `alembic upgrade head` against `DATABASE_URL` |
| `scripts/create_admin.py` | Bootstrap first admin user |
| `vercel.json` | Routes all traffic to the Python handler |

## Prerequisites

1. GitHub repo: `https://github.com/seyi-qing/ncof-platform.git`
2. Vercel project linked to that repo
3. Neon Postgres (migration chunk 08 completed)

## Environment variables (Vercel Production)

| Name | Value |
|------|--------|
| `APP_ENV` | `production` |
| `DATABASE_URL` | Neon connection string |
| `SECRET_KEY` | `openssl rand -hex 32` |
| `PAYMENT_WEBHOOK_SECRET` | different `openssl rand -hex 32` |
| `AUDIT_HASH_SECRET` | different `openssl rand -hex 32` |
| `CORS_ORIGINS` | Frontend origin e.g. `https://ncof.vercel.app` |

## Migration

```bash
export DATABASE_URL="postgresql+psycopg://..."
python scripts/migrate.py
```

Chain: 0001 → 0002 → 0003 → 0004 → 0005 → (0006_hardening + 0006_member_experience) → 0007_merge → 0008_election_voting

## Bootstrap admin

```bash
DATABASE_URL=... python scripts/create_admin.py admin@yourdomain.com 'YourStrongPassword12+'
```

## Smoke checks

- GET /health
- GET /ready
- GET /docs
