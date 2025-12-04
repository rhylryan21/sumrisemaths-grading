from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health():
    r = client.get("/")
    assert r.status_code == 200
    assert r.json().get("ok") is True


def test_evaluate_valid():
    r = client.post("/evaluate", json={"expr": "3^2 + 4^2"})
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert abs(data["value"] - 25.0) < 1e-9


def test_evaluate_invalid_chars():
    r = client.post("/evaluate", json={"expr": "abc"})
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is False
    assert "allowed" in data.get("feedback", "").lower()


def test_evaluate_len_limit():
    r = client.post("/evaluate", json={"expr": "1" * 101})
    data = r.json()
    assert data["ok"] is False
