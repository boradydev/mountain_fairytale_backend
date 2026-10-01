from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from src.app.common.abcs.services.event_publisher import IEventPublisher
from src.app.common.abcs.services.password_service import IPasswordService
from src.app.employees.usecases.change_password import ChangeEmployeePasswordUseCase
from src.app.employees.usecases.create import CreateEmployeeUseCase
from src.app.employees.usecases.deactivate import DeactivateEmployeeUseCase
from src.app.employees.usecases.get import GetEmployeeUseCase
from src.app.employees.usecases.get_all import GetEmployeesUseCase
from src.app.employees.usecases.update import UpdateEmployeeUseCase
from src.infra.db.postgres.uow.employees import EmployeesUOW


class EmployeesUseCaseFactory:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        event_publisher: IEventPublisher,
        password_service: IPasswordService,
    ) -> None:
        self._session_factory = session_factory
        self._event_publisher = event_publisher
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

    def deactivate_employee(self) -> DeactivateEmployeeUseCase:
        return DeactivateEmployeeUseCase(
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
            event_publisher=self._event_publisher,
        )