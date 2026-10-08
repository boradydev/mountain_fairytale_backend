from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.feat.clients.app.usecases.check_duplicate import CheckClientDuplicateUseCase
from src.feat.clients.app.usecases.create import CreateClientUseCase
from src.feat.clients.app.usecases.get import GetClientUseCase
from src.feat.clients.app.usecases.get_all import GetClientsUseCase
from src.feat.clients.app.usecases.update import UpdateClientUseCase
from src.feat.clients.infra.client_uow import ClientsUOW


class ClientsUseCaseFactory:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._session_factory = session_factory

    def create_client(self) -> CreateClientUseCase:
        return CreateClientUseCase(uow=self._create_uow())

    def get_client(self) -> GetClientUseCase:
        return GetClientUseCase(uow=self._create_uow())

    def get_clients(self) -> GetClientsUseCase:
        return GetClientsUseCase(uow=self._create_uow())

    def update_client(self) -> UpdateClientUseCase:
        return UpdateClientUseCase(uow=self._create_uow())

    def check_duplicate(self) -> CheckClientDuplicateUseCase:
        return CheckClientDuplicateUseCase(uow=self._create_uow())

    def _create_uow(self) -> ClientsUOW:
        return ClientsUOW(session_factory=self._session_factory)

    @property
    def create_uow(self) -> ClientsUOW:
        return self._create_uow()
