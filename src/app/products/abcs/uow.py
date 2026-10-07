from abc import ABC, abstractmethod

from src.app.common.abcs.uow import InterfaceUOW
from src.domain.products.abcs.products_repo_abcs import IProductsRepository


class IProductsUOW(InterfaceUOW, ABC):
    @property
    @abstractmethod
    def products(self) -> IProductsRepository:
        """Репозиторий товаров."""
