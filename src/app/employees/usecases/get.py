from dataclasses import dataclass
from uuid import UUID

from src.app.employees.abcs.uow import IEmployeesUOW
from src.domain.employees.entities import Employee
from src.domain.employees.excs import EmployeeNotFoundException


@dataclass(frozen=True, slots=True, kw_only=True)
class GetEmployeeDTO:
    employee_id: UUID


class GetEmployeeUseCase:
    def __init__(
        self,
        uow: IEmployeesUOW,
    ) -> None:
        self._uow = uow

    async def execute(
        self,
        dto: GetEmployeeDTO,
    ) -> Employee:
        async with self._uow as uow:
            employee = await uow.employees.get_by_id(
                dto.employee_id,
            )

            if employee is None:
                raise EmployeeNotFoundException(
                    employee_id=dto.employee_id,
                )

            return employee
