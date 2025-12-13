from fastapi.testclient import TestClient

from db import SessionLocal
from main import app
from models import Attempt

client = TestClient(app)


def test_mark_batch_records_duration_ms():
    r = client.post(
        "/mark-batch",
        json={"items": [{"id": "q1", "answer": "25"}, {"id": "q4", "answer": "3/4"}]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body.get("attempt_id") is not None
    attempt_id = body["attempt_id"]

    db = SessionLocal()
    try:
        a = db.query(Attempt).filter(Attempt.id == attempt_id).first()
        assert a is not None
        assert a.duration_ms is not None
        assert isinstance(a.duration_ms, int)
        assert a.duration_ms >= 0
    finally:
        db.close()
