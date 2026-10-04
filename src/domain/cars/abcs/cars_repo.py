from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.cars.entities import Car


class ICarsRepository(ABC):
    @abstractmethod
    async def add(
        self,
        car: Car,
    ) -> None:
        """Добавляет автомобиль."""

    @abstractmethod
    async def update(
        self,
        car: Car,
    ) -> None:
        """Сохраняет изменения автомобиля."""

    @abstractmethod
    async def get_by_id(
        self,
        car_id: UUID,
    ) -> Car | None:
        """Возвращает автомобиль по ID."""

    @abstractmethod
    async def get_all(
        self,
        include_deactivated: bool = False,
    ) -> list[Car]:
        """Возвращает все автомобили."""

    @abstractmethod
    async def get_by_number(
        self,
        number: str,
    ) -> Car | None:
        """Возвращает автомобиль по госномеру."""
