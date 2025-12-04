import os
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_admin_reload_unauthorized(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "secret")
    r = client.post("/admin/reload")
    assert r.status_code == 200 and r.json()["ok"] is False


def test_admin_reload_ok(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "secret")
    r = client.post("/admin/reload", headers={"x-admin-token": "secret"})
    assert r.status_code == 200 and r.json()["ok"] is True
