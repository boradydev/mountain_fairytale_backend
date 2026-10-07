from abc import ABC, abstractmethod

from src.common.app.abcs.uow_abcs import InterfaceUOW
from src.domain.employees.abcs.employees_repo import IEmployeesRepository


class IEmployeesUOW(InterfaceUOW, ABC):
    @property
    @abstractmethod
    def employees(self) -> IEmployeesRepository:
        """Репозиторий сотрудников."""
