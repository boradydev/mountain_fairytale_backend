from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.auth.usecases.login import LoginUseCase
from src.app.auth.usecases.refresh import RefreshUseCase
from src.app.common.abcs.services.password_service import IPasswordService
from src.feat.employees.infra.employee_uow import EmployeesUOW
from src.api.fastapi.common.api_abcs import ITokenService


class AuthUseCaseFactory:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        password_service: IPasswordService,
        token_service: ITokenService,
    ) -> None:
        self._session_factory = session_factory
        self._password_service = password_service
        self._token_service = token_service

    def login(self) -> LoginUseCase:
        return LoginUseCase(
            uow=self._create_uow(),
            password_service=self._password_service,
            token_service=self._token_service,
        )

    def refresh(self) -> RefreshUseCase:
        return RefreshUseCase(
            uow=self._create_uow(),
            token_service=self._token_service,
        )

    def _create_uow(self) -> EmployeesUOW:
        return EmployeesUOW(
            session_factory=self._session_factory,
        )
