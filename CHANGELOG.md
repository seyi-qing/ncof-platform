# Changelog — NCOF Platform API

All notable changes to this project are documented in this file.

Format: [Semantic Versioning](https://semver.org/) — `MAJOR.MINOR.PATCH`

## [1.8.0] — 2026-09-26

### Added
- `PATCH /members/me` — self-serve profile update (name, email, phone)
- `ProfileSelfUpdate` schema
- Dues list includes `member_name` and `member_no`
- Meeting attendance includes `member_name`

### Fixed
- Restored full `app/schemas.py` after incomplete push (API was returning `FUNCTION_INVOCATION_FAILED`)
- Membership status lockout for suspended members remains in place

### Compatible web
- Works with **ncof-platform-web v2.1.x**

## [1.7.0] — prior production baseline

- FastAPI + Neon Postgres + Alembic through election voting
- JWT auth, dues, finance, governance, elections, webhooks, audit

---

## How to release next

1. Bump `VERSION` and `app.version` in `app/main.py`
2. Add a section under this CHANGELOG
3. Commit to `main`
4. On GitHub: **Releases → Draft a new release → tag `v1.x.y`**
