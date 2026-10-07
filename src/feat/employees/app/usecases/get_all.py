from dataclasses import dataclass
from src.feat.employees.app.abcs.employee_uow_abcs import IEmployeesUOW
from src.feat.employees.domain.employee_entities import Employee


@dataclass(frozen=True, slots=True, kw_only=True)
class GetEmployeesDTO:
    include_deactivated: bool = False


class GetEmployeesUseCase:
    def __init__(
        self,
        uow: IEmployeesUOW,
    ) -> None:
        self._uow = uow

    async def execute(
        self,
        dto: GetEmployeesDTO,
    ) -> list[Employee]:
        async with self._uow as uow:
            return await uow.employees.get_all(
                include_deactivated=dto.include_deactivated,
            )
