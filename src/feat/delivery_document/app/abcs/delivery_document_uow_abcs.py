from abc import ABC, abstractmethod
from src.common.app.abcs.uow_abcs import InterfaceUOW
from src.feat.delivery_document.domain.abcs.delivery_document_repo_abcs import IDeliveryDocumentsRepository


class IDeliveryDocumentsUOW(InterfaceUOW, ABC):
    @property
    @abstractmethod
    def delivery_documents(self) -> IDeliveryDocumentsRepository: ...
