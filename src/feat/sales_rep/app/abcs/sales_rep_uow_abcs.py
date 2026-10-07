from abc import ABC, abstractmethod

from src.app.common.abcs.uow import InterfaceUOW
from src.feat.sales_rep.domain.abcs.sales_rep_repo_abcs import ISalesRepresentativesRepository


class ISalesRepresentativesUOW(InterfaceUOW, ABC):
    @property
    @abstractmethod
    def sales_representatives(self) -> ISalesRepresentativesRepository:
        """Репозиторий торговых представителей."""
