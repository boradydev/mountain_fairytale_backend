from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.feat.cars.app.abcs.uow import ICarsUOW
from src.feat.cars.domain.abcs.cars_repo_abcs import ICarsRepository
from src.feat.cars.infra.cars_repo import CarsRepository
from src.infra.db.postgres.uow.common import IPostgresUOW
from src.infra.services.event_publisher.service import EventPublisher


class CarsUOW(IPostgresUOW, ICarsUOW):
    _cars: ICarsRepository

    @property
    def cars(self) -> ICarsRepository:
        return self._cars

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

        self._cars = CarsRepository(
            session=self._session,
        )

        return self