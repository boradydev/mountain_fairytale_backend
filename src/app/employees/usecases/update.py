from dataclasses import dataclass
from uuid import UUID

from src.app.employees.abcs.uow import IEmployeesUOW
from src.domain.employees.employee_entities import Employee
from src.domain.employees.employee_excs import EmployeeNotFoundException


@dataclass(frozen=True, slots=True, kw_only=True)
class UpdateEmployeeDTO:
    actor_id: UUID
    employee_id: UUID
    payload: dict


class UpdateEmployeeUseCase:
    def __init__(
        self,
        uow: IEmployeesUOW,
    ) -> None:
        self._uow = uow

    async def execute(
        self,
        dto: UpdateEmployeeDTO,
    ) -> Employee:
        async with self._uow as uow:
            employee = await uow.employees.get_by_id(
                dto.employee_id,
            )

            if employee is None:
                raise EmployeeNotFoundException(
                    employee_id=dto.employee_id,
                )

            employee.update(
                actor_id=dto.actor_id,
                **dto.payload,
            )

            await uow.employees.update(employee)

            await uow.commit(
                events=employee.pull_events(),
            )

        return employee
