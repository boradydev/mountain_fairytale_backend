from abc import ABC, abstractmethod

from src.common.app.abcs.uow_abcs import InterfaceUOW
from src.feat.sales_rep.domain.abcs.sales_rep_repo_abcs import ISalesRepresentativesRepository


class ISalesRepresentativesUOW(InterfaceUOW, ABC):
    @property
    @abstractmethod
    def sales_representatives(self) -> ISalesRepresentativesRepository:
        """Репозиторий торговых представителей."""
