from dataclasses import dataclass

from src.app.auth.dto import AuthTokensDTO
from src.app.common.abcs.services.password_service import IPasswordService
from src.app.employees.abcs.uow import IEmployeesUOW
from src.domain.employees import employee_excs
from src.domain.employees.events import EmployeeLoginEvent
from src.api.fastapi.common.abcs import ITokenService


@dataclass(frozen=True, slots=True, kw_only=True)
class LoginDTO:
    username: str
    password: str


class LoginUseCase:
    def __init__(
        self,
        uow: IEmployeesUOW,
        password_service: IPasswordService,
        token_service: ITokenService,
    ) -> None:
        self._uow = uow
        self._password_service = password_service
        self._token_service = token_service

    async def execute(
        self,
        dto: LoginDTO,
    ) -> AuthTokensDTO:
        async with self._uow as uow:
            employee = await uow.employees.get_by_username(
                dto.username,
            )

            if employee is None:
                raise employee_excs.EmployeeNotFoundByUsernameException(
                    username=dto.username,
                )

            if not employee.is_active:
                raise employee_excs.EmployeeDeactivateException(
                    employee_id=employee.employee_id,
                )

            is_valid = self._password_service.verify_password(
                plain_password=dto.password,
                hashed_password=employee.password_hash,
            )

            if not is_valid:
                raise employee_excs.InvalidCredentialsException

            access_token = self._token_service.create_access_token(
                employee_id=str(employee.employee_id),
                role=employee.role,
            )

            refresh_token = self._token_service.create_refresh_token(
                employee_id=str(employee.employee_id),
            )

            await uow.commit(
                events=[
                    EmployeeLoginEvent(
                        actor_id=employee.employee_id,
                    ),
                ],
            )

            return AuthTokensDTO(
                access_token=access_token,
                refresh_token=refresh_token,
            )
