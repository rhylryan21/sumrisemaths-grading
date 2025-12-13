from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health_migrations_basic():
    r = client.get("/health/migrations")
    assert r.status_code == 200
    b = r.json()
    assert "code_heads" in b and isinstance(b["code_heads"], list)
    assert "db_version" in b
