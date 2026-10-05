from dataclasses import dataclass
from uuid import UUID

from src.app.common.abcs.services.password_service import IPasswordService
from src.app.employees.abcs.uow import IEmployeesUOW
from src.domain.employees.employee_excs import EmployeeNotFoundException


@dataclass(frozen=True, slots=True, kw_only=True)
class ChangeEmployeePasswordDTO:
    actor_id: UUID
    employee_id: UUID
    password: str


class ChangeEmployeePasswordUseCase:
    def __init__(
        self,
        uow: IEmployeesUOW,
        password_service: IPasswordService,
    ) -> None:
        self._uow = uow
        self._password_service = password_service

    async def execute(
        self,
        dto: ChangeEmployeePasswordDTO,
    ) -> None:
        password_hash = self._password_service.hash(
            password=dto.password,
        )

        async with self._uow as uow:
            employee = await uow.employees.get_by_id(
                dto.employee_id,
            )

            if employee is None:
                raise EmployeeNotFoundException(
                    employee_id=dto.employee_id,
                )

            employee.change_password(
                actor_id=dto.actor_id,
                new_password_hash=password_hash,
            )

            await uow.employees.update(employee)

            await uow.commit(
                events=employee.pull_events(),
            )
