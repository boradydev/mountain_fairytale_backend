from dataclasses import dataclass
from uuid import UUID

from src.app.auth.dto import AuthTokensDTO
from src.app.employees.abcs.uow import IEmployeesUOW
from src.domain.employees.employee_excs import EmployeeNotFoundException
from src.api.fastapi.common.abcs import ITokenService


@dataclass(frozen=True, slots=True, kw_only=True)
class RefreshDTO:
    refresh_token: str


class RefreshUseCase:
    def __init__(
        self,
        uow: IEmployeesUOW,
        token_service: ITokenService,
    ) -> None:
        self._uow = uow
        self._token_service = token_service

    async def execute(
        self,
        dto: RefreshDTO,
    ) -> AuthTokensDTO:
        payload = self._token_service.get_payload_refresh_token(
            refresh_token=dto.refresh_token,
        )

        employee_id = UUID(payload.employee_id)

        async with self._uow as uow:
            employee = await uow.employees.get_by_id(
                employee_id,
            )

            if employee is None or not employee.is_active:
                raise EmployeeNotFoundException

            access_token = self._token_service.create_access_token(
                employee_id=str(employee.employee_id),
                role=employee.role,
            )

            refresh_token = self._token_service.create_refresh_token(
                employee_id=str(employee.employee_id),
            )

            return AuthTokensDTO(
                access_token=access_token,
                refresh_token=refresh_token,
            )