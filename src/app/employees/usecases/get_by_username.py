from dataclasses import dataclass

from src.app.employees.abcs.uow import IEmployeesUOW
from src.domain.employees.entities import Employee
from src.domain.employees.excs import EmployeeNotFoundByUsernameException


@dataclass(frozen=True, slots=True, kw_only=True)
class GetEmployeeByUsernameDTO:
    username: str


class GetEmployeeByUsernameUseCase:
    def __init__(
        self,
        uow: IEmployeesUOW,
    ) -> None:
        self._uow = uow

    async def execute(
        self,
        dto: GetEmployeeByUsernameDTO,
    ) -> Employee:
        async with self._uow as uow:
            employee = await uow.employees.get_by_username(
                dto.username,
            )

            if employee is None:
                raise EmployeeNotFoundByUsernameException(
                    username=dto.username,
                )

            return employee
