from abc import ABC, abstractmethod

from src.common.app.abcs.uow_abcs import InterfaceUOW
from src.common.domain.abcs.event_repo_abcs import IEventRepository


class IAuditUOW(InterfaceUOW, ABC):
    @property
    @abstractmethod
    def events(self) -> IEventRepository:
        """Репозиторий аудита."""
