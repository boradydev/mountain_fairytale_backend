from abc import ABC, abstractmethod

from src.app.common.abcs.uow import InterfaceUOW
from src.domain.employees.abcs.repo import IEmployeesRepository


class IEmployeesUOW(InterfaceUOW, ABC):
    @property
    @abstractmethod
    def employees(self) -> IEmployeesRepository:
        """Репозиторий сотрудников."""
