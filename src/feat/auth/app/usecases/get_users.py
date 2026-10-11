from src.feat.employees.app.abcs.employee_uow_abcs import IEmployeesUOW


class GetAuthUsersUseCase:
    def __init__(self, uow: IEmployeesUOW) -> None:
        self._uow = uow

    async def execute(self) -> list[str]:
        async with self._uow as uow:
            return await uow.employees.get_active_usernames()
