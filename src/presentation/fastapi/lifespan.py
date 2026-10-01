from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.infra.db.postgres.database import Postgres
from src.infra.factories.employees import EmployeesUseCaseFactory
from src.infra.services.event_publisher.service import EventPublisher
from src.infra.services.password.service import PasswordService
from src.infra.services.token.service import JwtTokenService
from src.presentation.fastapi.common.app_context import AppContext


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управляет жизненным циклом ресурсов приложения."""
    postgres = Postgres()
    event_publisher = EventPublisher(
        session_factory=postgres.session_factory,
    )
    token_service = JwtTokenService()
    passwd_service = PasswordService()

    employees_use_cases = EmployeesUseCaseFactory(
        session_factory=postgres.session_factory,
        event_publisher=event_publisher,
        password_service=passwd_service,
    )

    ctx = AppContext(
        postgres_session_factory=postgres.session_factory,
        token_service=token_service,
        passwd_service=passwd_service,
        event_publisher=event_publisher,
        employees_use_cases=employees_use_cases,
    )

    app.state.ctx = ctx  # type: ignore[assignment]

    yield

    await event_publisher.wait_pending()
    await postgres.dispose()
