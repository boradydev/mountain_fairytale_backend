from abc import ABC, abstractmethod

from src.app.common.abcs.uow import InterfaceUOW
from src.domain.cars.abcs.cars_repo_abcs import ICarsRepository


class ICarsUOW(InterfaceUOW, ABC):
    @property
    @abstractmethod
    def cars(self) -> ICarsRepository:
        """Репозиторий автомобилей."""