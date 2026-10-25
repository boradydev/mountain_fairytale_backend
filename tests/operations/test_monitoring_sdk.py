import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.common.api.monitoring_routers import monitoring_router
from src.core.monitoring import _recent, private_event


def test_public_configuration_has_only_public_connection_fields(monkeypatch):
    app = FastAPI()
    app.include_router(monitoring_router, prefix="/public")
    monkeypatch.setenv("FLUTTER_MONITORING_ENABLED", "true")
    monkeypatch.setenv("FLUTTER_SENTRY_PUBLIC_KEY", "a" * 32)
    monkeypatch.setenv("FLUTTER_SENTRY_PROJECT_ID", "2")
    monkeypatch.setenv("SENTRY_DSN", "private-backend-dsn")
    data = TestClient(app).get("/public/monitoring/config").json()["data"]
    assert data["enabled"] is True
    assert data["publicKey"] == "a" * 32
    assert "private-backend-dsn" not in json.dumps(data)
    monkeypatch.setenv("GLITCHTIP_PORT", "invalid")
    assert TestClient(app).get("/public/monitoring/config").json()["data"]["enabled"] is False


def test_error_redaction_keeps_type_stack_and_version_without_secrets():
    _recent.clear()
    event = {
        "request": {"headers": {"Authorization": "secret-token"}, "data": "private-body"},
        "user": {"email": "private-email"}, "extra": {"password": "private-password"},
        "breadcrumbs": [{"message": "private-detail"}], "release": "backend@1.0.0",
        "exception": {"values": [{"type": "ValueError", "value": "private-value", "stacktrace": {
            "frames": [{"filename": "C:/Users/private-user/app.py", "function": "save", "lineno": 10,
                        "vars": {"password": "secret"}, "context_line": "private-code"}],
        }}]},
    }
    clean = private_event(event, {})
    serialized = json.dumps(clean)
    assert "private" not in serialized
    assert "secret" not in serialized
    assert clean["exception"]["values"][0]["stacktrace"]["frames"][0]["function"] == "save"
    assert clean["release"] == "backend@1.0.0"
    assert private_event(event, {}) is None
