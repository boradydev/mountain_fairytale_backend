from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.common.abcs.services.event_publisher import IEventPublisher
from src.domain.employees.abcs.repo import IEmployeesRepository
from src.infra.db.postgres.repos.employees.repo import EmployeesRepository
from src.infra.db.postgres.uow.common import IPostgresUOW


class EmployeesUOW(IPostgresUOW):
    _employees: IEmployeesRepository

    @property
    def employees(self) -> IEmployeesRepository:
        return self._employees

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        event_publisher: IEventPublisher,
    ) -> None:
        self._session_factory = session_factory
        self._event_publisher = event_publisher

    async def __aenter__(self) -> Self:
        self._session = self._session_factory()

        self._employees = EmployeesRepository(
            session=self._session,
        )

        return self