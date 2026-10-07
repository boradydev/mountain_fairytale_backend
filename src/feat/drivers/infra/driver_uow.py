from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.feat.drivers.app.abcs.driver_uow_abcs import IDriversUOW
from src.domain.drivers.abcs.drivers_repo_abcs import IDriversRepository
from src.feat.drivers.infra.driver_repos import DriversRepository
from src.common.infra.db.postgres.uow.common import IPostgresUOW
from src.common.infra.services.event_pud_service import EventPublisher


class DriversUOW(IPostgresUOW, IDriversUOW):
    _drivers: IDriversRepository

    @property
    def drivers(self) -> IDriversRepository:
        return self._drivers

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._session_factory = session_factory

    async def __aenter__(self) -> Self:
        self._session = self._session_factory()
        self._event_publisher = EventPublisher(
            session=self._session,
        )

        self._drivers = DriversRepository(
            session=self._session,
        )

        return self
