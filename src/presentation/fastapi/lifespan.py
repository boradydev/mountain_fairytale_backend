from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.infra.bootstrap.admins.ensure_admin import ensure_admin
from src.infra.db.postgres.database import Postgres
from src.infra.factories.employees import EmployeesUseCaseFactory
from src.infra.services.event_publisher.service import EventPublisher
from src.infra.services.password.service import PasswordService
from src.infra.services.token.service import JwtTokenService
from src.infra.factories.app_context import AppContext


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управляет жизненным циклом ресурсов приложения."""
    postgres = Postgres()
    token_service = JwtTokenService()
    passwd_service = PasswordService()

    employees_use_cases = EmployeesUseCaseFactory(
        session_factory=postgres.session_factory,
        password_service=passwd_service,
    )

    ctx = AppContext(
        postgres_session_factory=postgres.session_factory,
        token_service=token_service,
        passwd_service=passwd_service,
        employees_use_cases=employees_use_cases,
    )

    app.state.ctx = ctx  # type: ignore[assignment]

    await ensure_admin(
        password_service=passwd_service,
        uow=employees_use_cases.create_uow
    )

    yield

    await postgres.dispose()
