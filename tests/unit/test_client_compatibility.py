from pathlib import Path

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from src.common.api.client_compatibility import (
    ClientCompatibility,
    app_info_router,
    install_client_compatibility,
    parse_client_version,
    require_client_version,
)
from src.common.api.request_ids import install_request_ids


@pytest.fixture
def compatibility_app():
    app = FastAPI()
    install_client_compatibility(app, ClientCompatibility("1.9.0"))
    install_request_ids(app)
    app.include_router(app_info_router, prefix="/public")
    app.state.writes = 0

    @app.post("/protected/write", dependencies=[Depends(require_client_version)])
    def write():
        app.state.writes += 1
        return {"saved": True}

    return app


@pytest.mark.parametrize("version", ["1.9.0", "1.10.0", "2.0.0"])
def test_supported_versions_reach_operation(compatibility_app, version):
    response = TestClient(compatibility_app).post("/protected/write", headers={"X-Client-Version": version})
    assert response.status_code == 200
    assert compatibility_app.state.writes == 1


@pytest.mark.parametrize("version", [None, "", "1.0", "1.2.3+4", "01.2.3", "65536.0.0", "1.2.3\n"])
def test_invalid_header_does_not_reach_operation(compatibility_app, version):
    headers = {} if version is None else {"X-Client-Version": version}
    response = TestClient(compatibility_app).post("/protected/write", headers=headers)
    assert response.status_code == 400
    assert response.json()["code"] == "CLIENT_VERSION_INVALID"
    assert response.headers["X-Request-ID"]
    assert compatibility_app.state.writes == 0


def test_old_client_is_rejected_before_any_write(compatibility_app):
    response = TestClient(compatibility_app).post("/protected/write", headers={"X-Client-Version": "1.8.9"})
    assert response.status_code == 409
    assert response.json()["code"] == "CLIENT_UPDATE_REQUIRED"
    assert response.json()["minClientVersion"] == "1.9.0"
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Request-ID"]
    assert compatibility_app.state.writes == 0


def test_app_info_works_without_headers_and_tracks_installed_policy(compatibility_app):
    client = TestClient(compatibility_app)
    first = client.get("/public/app-info")
    assert first.status_code == 200
    assert first.json()["data"]["minClientVersion"] == "1.9.0"
    assert first.headers["Cache-Control"] == "no-store"
    compatibility_app.state.client_compatibility = ClientCompatibility("2.0.0")
    assert client.get("/public/app-info").json()["data"]["minClientVersion"] == "2.0.0"


@pytest.mark.parametrize("content", ['[flutter]\nmin_version = "bad"', '[flutter]\nmin_version = 1', "[other]"])
def test_bad_policy_prevents_startup(tmp_path: Path, content):
    path = tmp_path / "client_compatibility.toml"
    path.write_text(content, encoding="utf-8")
    with pytest.raises((ValueError, KeyError)):
        ClientCompatibility.load(path)


def test_checked_in_policy_is_valid():
    assert parse_client_version(ClientCompatibility.load().min_version)


@pytest.mark.parametrize("path", ["/public/auth/login", "/public/auth/refresh", "/protected/me", "/admin/employees"])
def test_real_app_checks_version_before_authentication(path):
    from src.common.api.app import fastapi_app

    client = TestClient(fastapi_app)
    response = client.request("POST" if path.startswith("/public") else "GET", path)
    assert response.status_code == 400
    assert response.json()["code"] == "CLIENT_VERSION_INVALID"
    assert response.headers["X-Request-ID"]


@pytest.mark.parametrize("path", ["/health/live", "/public/app-info", "/public/monitoring/config"])
def test_operational_routes_do_not_require_client_version(path):
    from src.common.api.app import fastapi_app

    assert TestClient(fastapi_app).get(path).status_code == 200
