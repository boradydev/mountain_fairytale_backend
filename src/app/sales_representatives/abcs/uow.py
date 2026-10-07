from abc import ABC, abstractmethod

from src.app.common.abcs.uow import InterfaceUOW
from src.domain.sales_representatives.abcs.sales_representatives_repo_abcs import ISalesRepresentativesRepository


class ISalesRepresentativesUOW(InterfaceUOW, ABC):
    @property
    @abstractmethod
    def sales_representatives(self) -> ISalesRepresentativesRepository:
        """Репозиторий торговых представителей."""
