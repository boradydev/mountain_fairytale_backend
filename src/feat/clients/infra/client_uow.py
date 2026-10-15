from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.common.app.abcs.uow_abcs import CommittedEventsHandler
from src.common.infra.db.postgres.common import IPostgresUOW
from src.common.infra.services.event_pud_service import EventPublisher
from src.feat.clients.app.abcs.client_uow_abcs import IClientsUOW
from src.feat.clients.domain.abcs.client_repo_abcs import IClientsRepository
from src.feat.clients.infra.client_repos import ClientsRepository


class ClientsUOW(IPostgresUOW, IClientsUOW):
    _clients: IClientsRepository

    @property
    def clients(self) -> IClientsRepository:
        return self._clients

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        on_committed: CommittedEventsHandler | None,
    ) -> None:
        self._session_factory = session_factory
        self._on_committed = on_committed

    async def __aenter__(self) -> Self:
        self._session = self._session_factory()
        self._event_publisher = EventPublisher(session=self._session)
        self._clients = ClientsRepository(session=self._session)
        return self
