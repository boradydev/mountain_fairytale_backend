from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.feat.delivery_document.app.usecases.change_status import ChangeDeliveryDocumentStatusUseCase
from src.feat.delivery_document.app.usecases.create import CreateDeliveryDocumentUseCase
from src.feat.delivery_document.app.usecases.edit_lock import DeliveryDocumentEditLockUseCase
from src.feat.delivery_document.app.usecases.get import GetDeliveryDocumentUseCase
from src.feat.delivery_document.app.usecases.get_all import GetDeliveryDocumentsUseCase
from src.feat.delivery_document.app.usecases.update import UpdateDeliveryDocumentUseCase
from src.feat.delivery_document.infra.delivery_document_uow import DeliveryDocumentsUOW


class DeliveryDocumentsUseCaseFactory:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    def create_delivery_document(self) -> CreateDeliveryDocumentUseCase:
        return CreateDeliveryDocumentUseCase(uow=self._create_uow())

    def get_delivery_document(self) -> GetDeliveryDocumentUseCase:
        return GetDeliveryDocumentUseCase(uow=self._create_uow())

    def get_delivery_documents(self) -> GetDeliveryDocumentsUseCase:
        return GetDeliveryDocumentsUseCase(uow=self._create_uow())

    def update_delivery_document(self) -> UpdateDeliveryDocumentUseCase:
        return UpdateDeliveryDocumentUseCase(uow=self._create_uow())

    def cancel_delivery_document(self) -> ChangeDeliveryDocumentStatusUseCase:
        return ChangeDeliveryDocumentStatusUseCase(uow=self._create_uow(), restore=False)

    def restore_delivery_document(self) -> ChangeDeliveryDocumentStatusUseCase:
        return ChangeDeliveryDocumentStatusUseCase(uow=self._create_uow(), restore=True)

    def acquire_edit_lock(self) -> DeliveryDocumentEditLockUseCase:
        return DeliveryDocumentEditLockUseCase(uow=self._create_uow(), operation="acquire")

    def renew_edit_lock(self) -> DeliveryDocumentEditLockUseCase:
        return DeliveryDocumentEditLockUseCase(uow=self._create_uow(), operation="renew")

    def release_edit_lock(self) -> DeliveryDocumentEditLockUseCase:
        return DeliveryDocumentEditLockUseCase(uow=self._create_uow(), operation="release")

    def _create_uow(self) -> DeliveryDocumentsUOW:
        return DeliveryDocumentsUOW(session_factory=self._session_factory)

    @property
    def create_uow(self) -> DeliveryDocumentsUOW:
        return self._create_uow()
