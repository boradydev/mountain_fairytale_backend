from collections.abc import AsyncGenerator, Callable
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.fastapi.app import fastapi_app
from src.api.fastapi.common.api_abcs import ITokenService
from src.infra.db.postgres.database import Postgres
from src.infra.services.token.jwt_service import JwtTokenService
from src.infra.services.token.settings import JwtSettings


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, Any]:
    """Асинхронный HTTP-клиент с полноценным lifecycle FastAPI-приложения."""

    async with fastapi_app.router.lifespan_context(fastapi_app):
        transport = ASGITransport(app=fastapi_app)

        async with AsyncClient(
            transport=transport,
            base_url="http://testserver/api/v1",
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
