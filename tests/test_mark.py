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


def test_mark_simplify_fraction_correct():
    r = client.post("/mark", json={"id": "q4", "answer": "3/4"})
    b = r.json()
    assert b["ok"] and b["correct"] and b["score"] == 1
    assert b.get("expected_str") == "3/4"


def test_mark_simplify_fraction_equivalent_decimal():
    r = client.post("/mark", json={"id": "q4", "answer": "0.75"})
    b = r.json()
    assert b["ok"] and b["correct"]


def test_mark_simplify_fraction_not_reduced():
    r = client.post("/mark", json={"id": "q4", "answer": "6/8"})
    b = r.json()
    assert b["ok"] and not b["correct"] and b["score"] == 0


def test_mark_simplify_fraction_negative_incorrect():
    r = client.post("/mark", json={"id": "q4", "answer": "-3/4"})
    b = r.json()
    assert b["ok"] and not b["correct"] and b["score"] == 0
    # shows the canonical expected positive answer
    assert b.get("expected") == "3/4"


def test_mark_simplify_fraction_negative_decimal_incorrect():
    r = client.post("/mark", json={"id": "q4", "answer": "-0.75"})
    b = r.json()
    assert b["ok"] and not b["correct"] and b["score"] == 0
    assert b.get("expected") == "3/4"


def test_mark_simplify_fraction_negative_not_reduced_incorrect():
    r = client.post("/mark", json={"id": "q4", "answer": "-6/8"})
    b = r.json()
    assert b["ok"] and not b["correct"] and b["score"] == 0
    # no "reduce" hint because the value is wrong sign; we just show expected
    assert b.get("expected") == "3/4"
    assert (b.get("feedback") or "") == ""
