from abc import ABC, abstractmethod

from src.common.app.abcs.uow_abcs import InterfaceUOW
from src.feat.drivers.domain.abcs.driver_repo_abcs import IDriversRepository


class IDriversUOW(InterfaceUOW, ABC):
    @property
    @abstractmethod
    def drivers(self) -> IDriversRepository:
        """Репозиторий водителей."""
