from abc import ABC, abstractmethod
from uuid import UUID

from src.feat.employees.domain.employee_entities import Employee


class IEmployeesRepository(ABC):
    @abstractmethod
    async def add(self, employee: Employee) -> None:
        """Добавляет нового сотрудника."""

    @abstractmethod
    async def update(self, employee: Employee) -> None:
        """Сохраняет изменения сотрудника."""

    @abstractmethod
    async def get_by_id(
        self,
        employee_id: UUID,
    ) -> Employee | None:
        """Возвращает сотрудника по идентификатору."""

    @abstractmethod
    async def get_by_username(
        self,
        username: str,
    ) -> Employee | None:
        """Возвращает сотрудника по имени пользователя."""

    @abstractmethod
    async def get_all(
        self,
        include_deactivated: bool,
    ) -> list[Employee]:
        """Возвращает всех сотрудников."""
