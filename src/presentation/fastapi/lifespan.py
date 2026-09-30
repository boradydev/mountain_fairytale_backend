from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.infra.db.postgres.database import Postgres
from src.presentation.fastapi.common.app_context import AppContext
from src.infra.services.password.service import PasswordService
from src.infra.services.token.service import JwtTokenService


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управляет жизненным циклом ресурсов приложения."""
    postgres = Postgres()
    token_service = JwtTokenService()
    passwd_service = PasswordService()

    ctx = AppContext(
        postgres_session_factory=postgres.session_factory,
        token_service=token_service,
        passwd_service=passwd_service,
    )

    app.state.ctx = ctx  # type: ignore[assignment]
    yield
    await postgres.dispose()
