from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.sales_representatives.abcs.uow import ISalesRepresentativesUOW
from src.domain.sales_representatives.abcs.sales_representatives_repo_abcs import ISalesRepresentativesRepository
from src.infra.db.postgres.repos.sales_representatives.sales_representatives_repo import SalesRepresentativesRepository
from src.infra.db.postgres.uow.common import IPostgresUOW
from src.infra.services.event_publisher.service import EventPublisher


class SalesRepresentativesUOW(IPostgresUOW, ISalesRepresentativesUOW):
    _sales_representatives: ISalesRepresentativesRepository

    @property
    def sales_representatives(self) -> ISalesRepresentativesRepository:
        return self._sales_representatives

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

        self._sales_representatives = SalesRepresentativesRepository(
            session=self._session,
        )

        return self
