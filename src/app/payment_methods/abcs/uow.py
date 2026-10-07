from abc import ABC, abstractmethod

from src.app.common.abcs.uow import InterfaceUOW
from src.domain.payment_methods.abcs.payment_methods_repo_abcs import IPaymentMethodsRepository


class IPaymentMethodsUOW(InterfaceUOW, ABC):
    @property
    @abstractmethod
    def payment_methods(self) -> IPaymentMethodsRepository:
        """Репозиторий способов оплаты."""
