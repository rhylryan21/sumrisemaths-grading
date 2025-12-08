from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_get_attempt_roundtrip():
    # create one
    r = client.post("/mark-batch", json={"items": [{"id": "q1", "answer": "25"}]})
    assert r.status_code == 200
    attempt_id = r.json().get("attempt_id")
    assert isinstance(attempt_id, int)

    # read it back
    r2 = client.get(f"/attempts/{attempt_id}")
    assert r2.status_code == 200
    body = r2.json()
    assert body["id"] == attempt_id
    assert body["total"] == 1
    assert "created_at" in body
