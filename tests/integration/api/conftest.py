import os
from collections.abc import AsyncGenerator, Callable, Generator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from src.core.paths import PROJECT_DIR
from src.common.api.api_abcs import ITokenService
from src.common.api.app import fastapi_app
from src.common.infra.services.token.jwt_service import JwtTokenService
from src.common.infra.services.token.settings import JwtSettings
from tests.integration.db_helpers import bootstrap_test_database

ALEMBIC_CONFIG = PROJECT_DIR / "src" / "common" / "infra" / "db" / "postgres" / "alembic" / "alembic.ini"


@pytest.fixture(scope="session", autouse=True)
def prepare_api_database() -> Generator[None]:
    """Готовит изолированную базу данных специально для API / End-to-End тестов."""
    # Берем имя из POSTGRES_API_TEST_DB или задаем дефолт
    api_db_name = os.environ.get("POSTGRES_API_TEST_DB", "mountain_fairytale_api_test")

    os.environ["POSTGRES_DB"] = api_db_name # подмена названия базы в окружении

    bootstrap_test_database(test_db_name=api_db_name, alembic_config_path=ALEMBIC_CONFIG, project_dir=PROJECT_DIR)
    yield


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, Any]:
    """Асинхронный HTTP-клиент с полноценным lifecycle FastAPI-приложения."""
    async with fastapi_app.router.lifespan_context(fastapi_app):
        transport = ASGITransport(app=fastapi_app)

        async with AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            yield client


@pytest.fixture
def token_service_factory() -> Callable[..., ITokenService]:
    """Фабрика реального JWT-сервиса для специальных сценариев тестов."""

    def factory(
        access_expire: int = 1,
        refresh_expire: int = 1,
    ) -> ITokenService:
        return JwtTokenService(
            settings=JwtSettings(
                ACCESS_TOKEN_EXPIRE_SECONDS=access_expire,
                REFRESH_TOKEN_EXPIRE_SECONDS=refresh_expire,
            ),
        )

    return factory
