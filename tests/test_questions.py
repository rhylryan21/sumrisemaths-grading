# services/grading/tests/test_questions.py
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_get_question_detail_ok():
    r = client.get("/questions/q1")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "q1"
    assert "prompt" in body


def test_get_question_detail_404():
    r = client.get("/questions/missing")
    assert r.status_code == 404
