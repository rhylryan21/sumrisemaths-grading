from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_list_questions():
    r = client.get("/questions")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list) and len(data) >= 1
    q = data[0]
    assert {"id", "topic", "prompt", "type"}.issubset(q.keys())


def test_mark_correct_numeric():
    r = client.post("/mark", json={"id": "q1", "answer": "25"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["correct"] is True and body["score"] == 1


def test_mark_incorrect_numeric():
    r = client.post("/mark", json={"id": "q1", "answer": "24"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["correct"] is False and body["score"] == 0


def test_mark_invalid_chars():
    r = client.post("/mark", json={"id": "q1", "answer": "abc"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert "allowed" in body.get("feedback", "").lower()


def test_mark_unknown_id():
    r = client.post("/mark", json={"id": "nope", "answer": "1"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False and body["score"] == 0
