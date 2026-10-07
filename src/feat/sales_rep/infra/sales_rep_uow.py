from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.feat.sales_rep.app.abcs.sales_rep_uow_abcs import ISalesRepresentativesUOW
from src.feat.sales_rep.domain.abcs.sales_rep_repo_abcs import ISalesRepresentativesRepository
from src.feat.sales_rep.infra.sales_rep_repos import SalesRepresentativesRepository
from src.common.infra.db.postgres.uow.common import IPostgresUOW
from src.common.infra.services.event_pud_service import EventPublisher


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
