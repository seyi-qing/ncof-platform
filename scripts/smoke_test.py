import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

"""Local smoke test for import, health and database readiness."""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
assert client.get("/health").status_code == 200
print(client.get("/health").json())
