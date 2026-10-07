import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.infra.bootstrap.admins.ensure_admin import ensure_admin
from src.infra.db.postgres.database import Postgres
from src.infra.factories.app_context import AppContext
from src.infra.factories.auth import AuthUseCaseFactory
from src.infra.factories.cars import CarsUseCaseFactory
from src.infra.factories.drivers import DriversUseCaseFactory
from src.infra.factories.employees import EmployeesUseCaseFactory
from src.infra.factories.payment_methods import PaymentMethodsUseCaseFactory
from src.infra.factories.sales_representatives import SalesRepresentativesUseCaseFactory
from src.infra.services.password.service import PasswordService
from src.infra.services.token.jwt_service import JwtTokenService
from src.infra.services.token.settings import JwtSettings


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управляет жизненным циклом ресурсов приложения."""
    logger.info("Starting Fastapi application...")

    postgres = Postgres()

    token_settings = JwtSettings()
    token_service = JwtTokenService(settings=token_settings)

    passwd_service = PasswordService()

    employees_use_cases = EmployeesUseCaseFactory(
        session_factory=postgres.session_factory,
        password_service=passwd_service,
    )

    auth_use_cases = AuthUseCaseFactory(
        session_factory=postgres.session_factory,
        password_service=passwd_service,
        token_service=token_service,
    )

    cars_use_cases = CarsUseCaseFactory(
        session_factory=postgres.session_factory,
    )

    drivers_use_cases = DriversUseCaseFactory(
        session_factory=postgres.session_factory,
    )

    payment_methods_use_cases = PaymentMethodsUseCaseFactory(
        session_factory=postgres.session_factory,
    )

    sales_representatives_use_cases = SalesRepresentativesUseCaseFactory(
        session_factory=postgres.session_factory,
    )

    ctx = AppContext(
        postgres_session_factory=postgres.session_factory,
        token_service=token_service,
        passwd_service=passwd_service,
        employees_use_cases=employees_use_cases,
        auth_use_cases=auth_use_cases,
        cars_use_cases=cars_use_cases,
        drivers_use_cases=drivers_use_cases,
        payment_methods_use_cases=payment_methods_use_cases,
        sales_representatives_use_cases=sales_representatives_use_cases,
        token_settings=token_settings,
    )

    app.state.ctx = ctx  # type: ignore[assignment]

    await ensure_admin(password_service=passwd_service, uow=employees_use_cases.create_uow)

    yield

    await postgres.dispose()
