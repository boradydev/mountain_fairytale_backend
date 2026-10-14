from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.feat.audit_event.app.get_events import GetEventsUseCase
from src.feat.audit_event.infra.audit_uow import AuditUOW


class AuditUseCaseFactory:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    def get_events(self) -> GetEventsUseCase:
        return GetEventsUseCase(uow=AuditUOW(self._session_factory))
