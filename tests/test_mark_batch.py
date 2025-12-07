from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_mark_batch_basic():
    r = client.post(
        "/mark-batch", json={"items": [{"id": "q1", "answer": "25"}, {"id": "q4", "answer": "6/8"}]}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["total"] == 2
    assert isinstance(body["results"], list) and len(body["results"]) == 2
