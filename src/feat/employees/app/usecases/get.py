from dataclasses import dataclass
from uuid import UUID

from src.feat.employees.app.abcs.employee_uow_abcs import IEmployeesUOW
from src.feat.employees.domain.employee_entities import Employee
from src.feat.employees.domain.employee_excs import EmployeeNotFoundException


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
