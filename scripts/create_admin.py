import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

"""Create the first NCOF administrator.

Usage:
  DATABASE_URL=... python scripts/create_admin.py admin@example.com "StrongPassword"
"""
import sys
from sqlalchemy import select

from app.db import SessionLocal
from app.models import User
from app.security import hash_password


def main():
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python scripts/create_admin.py EMAIL PASSWORD")
    email = sys.argv[1].strip().lower()
    password = sys.argv[2]
    if len(password) < 12:
        raise SystemExit("Password must be at least 12 characters")
    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.email == email))
        if existing:
            raise SystemExit("A user with that email already exists")
        db.add(User(email=email, password_hash=hash_password(password), role="admin", is_active=True))
        db.commit()
    print(f"Created admin user: {email}")


if __name__ == "__main__":
    main()
