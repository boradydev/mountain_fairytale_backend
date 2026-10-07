from abc import ABC, abstractmethod

from src.common.app.abcs.uow_abcs import InterfaceUOW
from src.feat.employees.domain.abcs.employee_repo_abcs import IEmployeesRepository


class IEmployeesUOW(InterfaceUOW, ABC):
    @property
    @abstractmethod
    def employees(self) -> IEmployeesRepository:
        """Репозиторий сотрудников."""
