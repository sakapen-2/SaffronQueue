import os
import sys
from pathlib import Path
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

sys.path.append(str(Path(__file__).resolve().parents[1] / "api"))

from app.main import app  # noqa: E402

client = TestClient(app)

def test_healthz():
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["ok"] is True
