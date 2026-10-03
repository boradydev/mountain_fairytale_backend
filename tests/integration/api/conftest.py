import pytest
from starlette.testclient import TestClient

from src.api.fastapi.app import fastapi_app
from src.infra.bootstrap.admins.settings import AdminSettings


@pytest.fixture
def admin_settings() -> AdminSettings:
    return AdminSettings()


@pytest.fixture
def client():
    # Конструкция with гарантирует выполнение startup/lifespan событий приложения
    with TestClient(fastapi_app, base_url="http://testserver/api/v1") as c:
        yield c
