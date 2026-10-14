from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.common.domain.abcs.event_repo_abcs import IEventRepository
from src.common.infra.db.postgres.common import IPostgresUOW
from src.common.infra.db.postgres.repos.events.event_repos import EventsRepository
from src.common.infra.services.event_pud_service import EventPublisher
from src.feat.audit_event.app.abcs.audit_uow_abcs import IAuditUOW


class AuditUOW(IPostgresUOW, IAuditUOW):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    @property
    def events(self) -> IEventRepository:
        return self._events

    async def __aenter__(self) -> Self:
        self._session = self._session_factory()
        self._events = EventsRepository(self._session)
        self._event_publisher = EventPublisher(self._session)
        return self
