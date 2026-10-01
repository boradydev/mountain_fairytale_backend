from src.app.employees.abcs.uow import IEmployeesUOW
from src.domain.employees.entities import Employee


class GetEmployeesUseCase:
    def __init__(
        self,
        uow: IEmployeesUOW,
    ) -> None:
        self._uow = uow

    async def execute(self) -> list[Employee]:
        async with self._uow as uow:
            return await uow.employees.get_all()
