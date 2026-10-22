from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import OperationalError

from src.common.api.health_routers import get_health_database, health_router
from src.core.build_info import APP_VERSION


@pytest.mark.parametrize("path", ["/health/live", "/health/ready"])
async def test_health_checks_are_public_and_do_not_expose_secrets(path: str) -> None:
    database = AsyncMock()
    app = FastAPI()
    app.include_router(health_router)
    app.dependency_overrides[get_health_database] = lambda: database
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(path)
    assert response.status_code == 200
    assert response.json()["data"]["version"] == APP_VERSION
    assert set(response.json()["data"]) == {"status", "version", "commitSha"}
    if path.endswith("ready"):
        database.check_connection.assert_awaited_once_with()
    else:
        database.check_connection.assert_not_awaited()


async def test_readiness_failure_returns_503_without_database_error_details() -> None:
    database = AsyncMock()
    database.check_connection.side_effect = OperationalError("secret SQL", {}, Exception("secret password"))
    app = FastAPI()
    app.include_router(health_router)
    app.dependency_overrides[get_health_database] = lambda: database
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health/ready")
        live = await client.get("/health/live")
    assert response.status_code == 503
    assert response.json()["data"]["status"] == "unavailable"
    assert "secret" not in response.text
    assert live.status_code == 200
