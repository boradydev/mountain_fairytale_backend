from abc import ABC, abstractmethod

from src.common.app.abcs.uow_abcs import InterfaceUOW
from src.feat.clients.domain.abcs.client_repo_abcs import IClientsRepository


class IClientsUOW(InterfaceUOW, ABC):
    @property
    @abstractmethod
    def clients(self) -> IClientsRepository:
        """Репозиторий клиентов."""
