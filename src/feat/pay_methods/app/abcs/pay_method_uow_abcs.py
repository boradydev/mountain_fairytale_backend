from abc import ABC, abstractmethod

from src.common.app.abcs.uow_abcs import InterfaceUOW
from src.domain.pay_methods.abcs.payment_methods_repo_abcs import IPaymentMethodsRepository


class IPaymentMethodsUOW(InterfaceUOW, ABC):
    @property
    @abstractmethod
    def payment_methods(self) -> IPaymentMethodsRepository:
        """Репозиторий способов оплаты."""
