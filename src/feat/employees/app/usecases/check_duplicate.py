from dataclasses import dataclass

from src.feat.employees.app.abcs.employee_uow_abcs import IEmployeesUOW
from src.feat.employees.domain.employee_entities import Employee


@dataclass(frozen=True, slots=True, kw_only=True)
class CheckEmployeeDuplicateDTO:
    username: str


class CheckEmployeeDuplicateUseCase:
    def __init__(self, uow: IEmployeesUOW) -> None:
        self._uow = uow

    async def execute(self, dto: CheckEmployeeDuplicateDTO) -> Employee | None:
        async with self._uow as uow:
            return await uow.employees.get_by_username(dto.username)
