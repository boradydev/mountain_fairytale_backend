from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.common.infra.db.postgres.common import IPostgresUOW
from src.common.infra.services.event_pud_service import EventPublisher
from src.feat.delivery_document.app.abcs.delivery_document_uow_abcs import (
    IDeliveryDocumentsUOW,
)
from src.feat.delivery_document.domain.abcs.delivery_document_repo_abcs import (
    IDeliveryDocumentsRepository,
)
from src.feat.delivery_document.infra.delivery_document_repos import (
    DeliveryDocumentsRepository,
)


class DeliveryDocumentsUOW(IPostgresUOW, IDeliveryDocumentsUOW):
    _delivery_documents: IDeliveryDocumentsRepository

    @property
    def delivery_documents(self) -> IDeliveryDocumentsRepository:
        return self._delivery_documents

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._session_factory = session_factory

    async def __aenter__(self) -> Self:
        self._session = self._session_factory()
        self._event_publisher = EventPublisher(session=self._session)
        self._delivery_documents = DeliveryDocumentsRepository(
            session=self._session,
        )
        return self
