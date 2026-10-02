from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.common.abcs.services.password_service import IPasswordService
from src.infra.factories.auth import AuthUseCaseFactory
from src.infra.factories.cars import CarsUseCaseFactory
from src.infra.factories.employees import EmployeesUseCaseFactory
from src.infra.services.token.settings import JwtSettings
from src.presentation.fastapi.common.abcs import ITokenService


@dataclass(frozen=True, slots=True)
class AppContext:
    postgres_session_factory: async_sessionmaker[AsyncSession]
    token_service: ITokenService
    passwd_service: IPasswordService

    employees_use_cases: EmployeesUseCaseFactory
    auth_use_cases: AuthUseCaseFactory
    cars_use_cases: CarsUseCaseFactory

    token_settings: JwtSettings