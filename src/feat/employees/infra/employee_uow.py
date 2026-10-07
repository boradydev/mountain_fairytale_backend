from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.feat.employees.app.abcs.employee_uow_abcs import IEmployeesUOW
from src.domain.employees.abcs.employees_repo import IEmployeesRepository
from src.feat.employees.infra.employee_repos import EmployeesRepository
from src.infra.db.postgres.uow.common import IPostgresUOW
from src.infra.services.event_publisher.service import EventPublisher


class EmployeesUOW(IPostgresUOW, IEmployeesUOW):
    _employees: IEmployeesRepository

    @property
    def employees(self) -> IEmployeesRepository:
        return self._employees

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._session_factory = session_factory

    async def __aenter__(self) -> Self:
        self._session = self._session_factory()
        self._event_publisher = EventPublisher(session=self._session)

        self._employees = EmployeesRepository(
            session=self._session,
        )

        return self
