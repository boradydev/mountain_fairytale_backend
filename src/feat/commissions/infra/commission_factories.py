from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.common.app.abcs.uow_abcs import CommittedEventsHandler
from src.feat.commissions.app.commission_usecases import AssignRepresentativeClientsUseCase, GetCommissionsUseCase
from src.feat.commissions.infra.commission_uow import CommissionsUOW


class CommissionsUseCaseFactory:
    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession], *, on_committed: CommittedEventsHandler | None
    ) -> None:
        self._session_factory = session_factory
        self._on_committed = on_committed

    def _uow(self) -> CommissionsUOW:
        return CommissionsUOW(self._session_factory, on_committed=self._on_committed)

    def get_report(self) -> GetCommissionsUseCase:
        return GetCommissionsUseCase(self._uow())

    def assign_clients(self) -> AssignRepresentativeClientsUseCase:
        return AssignRepresentativeClientsUseCase(self._uow())
