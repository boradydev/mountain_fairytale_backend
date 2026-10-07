from abc import ABC, abstractmethod

from src.app.common.abcs.uow import InterfaceUOW
from src.feat.cars.domain.abcs.car_repo_abcs import ICarsRepository


class ICarsUOW(InterfaceUOW, ABC):
    @property
    @abstractmethod
    def cars(self) -> ICarsRepository:
        """Репозиторий автомобилей."""