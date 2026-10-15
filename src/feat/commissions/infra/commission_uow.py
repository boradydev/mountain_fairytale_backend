from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.common.app.abcs.uow_abcs import CommittedEventsHandler
from src.common.infra.db.postgres.common import IPostgresUOW
from src.common.infra.services.event_pud_service import EventPublisher
from src.feat.commissions.app.commission_uow_abcs import ICommissionsUOW
from src.feat.commissions.domain.commission_repo_abcs import ICommissionsRepository
from src.feat.commissions.infra.commission_repos import CommissionsRepository


class CommissionsUOW(IPostgresUOW, ICommissionsUOW):
    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession], *, on_committed: CommittedEventsHandler | None
    ) -> None:
        self._session_factory = session_factory
        self._on_committed = on_committed

    async def __aenter__(self) -> Self:
        self._session = self._session_factory()
        self._event_publisher = EventPublisher(self._session)
        self._commissions = CommissionsRepository(self._session)
        return self

    @property
    def commissions(self) -> ICommissionsRepository:
        return self._commissions
