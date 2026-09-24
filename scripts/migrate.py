import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

"""Run Alembic migrations against the configured DATABASE_URL."""
from alembic import command
from alembic.config import Config


if __name__ == "__main__":
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    print("Database migrated to head.")
