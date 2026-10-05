from dataclasses import dataclass
from uuid import UUID

from src.app.common.abcs.services.password_service import IPasswordService
from src.app.employees.abcs.uow import IEmployeesUOW
from src.domain.employees.employee_entities import Employee


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateEmployeeDTO:
    actor_id: UUID
    username: str
    password: str
    role: str = "employee"


class CreateEmployeeUseCase:
    def __init__(
        self,
        uow: IEmployeesUOW,
        password_service: IPasswordService,
    ) -> None:
        self._uow = uow
        self._password_service = password_service

    async def execute(
        self,
        dto: CreateEmployeeDTO,
    ) -> Employee:
        password_hash = self._password_service.hash(
            password=dto.password,
        )

        employee = Employee.create(
            actor_id=dto.actor_id,
            username=dto.username,
            password_hash=password_hash,
            role=dto.role,
        )

        async with self._uow as uow:
            await uow.employees.add(employee)

            await uow.commit(
                events=employee.pull_events(),
            )

        return employee