from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from src.app.common.abcs.services.password_service import IPasswordService
from src.feat.employees.app.usecases.change_password import ChangeEmployeePasswordUseCase
from src.feat.employees.app.usecases.create import CreateEmployeeUseCase
from src.feat.employees.app.usecases.get import GetEmployeeUseCase
from src.feat.employees.app.usecases.get_all import GetEmployeesUseCase
from src.feat.employees.app.usecases.update import UpdateEmployeeUseCase
from src.feat.employees.infra.employee_uow import EmployeesUOW


class EmployeesUseCaseFactory:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        password_service: IPasswordService,
    ) -> None:
        self._session_factory = session_factory
        self._password_service = password_service

    def create_employee(self) -> CreateEmployeeUseCase:
        return CreateEmployeeUseCase(
            uow=self._create_uow(),
            password_service=self._password_service,
        )

    def update_employee(self) -> UpdateEmployeeUseCase:
        return UpdateEmployeeUseCase(
            uow=self._create_uow(),
        )

    def change_employee_password(self) -> ChangeEmployeePasswordUseCase:
        return ChangeEmployeePasswordUseCase(
            uow=self._create_uow(),
            password_service=self._password_service,
        )

    def get_employee(self) -> GetEmployeeUseCase:
        return GetEmployeeUseCase(
            uow=self._create_uow(),
        )

    def get_employees(self) -> GetEmployeesUseCase:
        return GetEmployeesUseCase(
            uow=self._create_uow(),
        )

    def _create_uow(self) -> EmployeesUOW:
        return EmployeesUOW(
            session_factory=self._session_factory,
        )

    @property
    def create_uow(self) -> EmployeesUOW:
        return self._create_uow()