import pytest
from starlette.testclient import TestClient

from src.api.fastapi.app import fastapi_app
from src.api.fastapi.common.abcs import ITokenService
from src.infra.bootstrap.admins.settings import AdminSettings
from src.infra.services.token.jwt_service import JwtTokenService
from src.infra.services.token.settings import JwtSettings


@pytest.fixture
def admin_settings() -> AdminSettings:
    return AdminSettings()


@pytest.fixture
def client():
    # Конструкция with гарантирует выполнение startup/lifespan событий приложения
    with TestClient(fastapi_app, base_url="http://testserver/api/v1") as c:
        yield c


def token_service_factory(access_expire: int = 1, refresh_expire: int = 1) -> ITokenService:
    return JwtTokenService(
        settings=JwtSettings(
            ACCESS_TOKEN_EXPIRE_SECONDS=access_expire,
            REFRESH_TOKEN_EXPIRE_SECONDS=refresh_expire,
        )
    )
