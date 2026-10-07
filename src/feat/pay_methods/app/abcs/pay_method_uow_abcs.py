from abc import ABC, abstractmethod

from src.common.app.abcs.uow_abcs import InterfaceUOW
from src.feat.pay_methods.domain.abcs.pay_method_repo_abcs import IPaymentMethodsRepository


class IPaymentMethodsUOW(InterfaceUOW, ABC):
    @property
    @abstractmethod
    def payment_methods(self) -> IPaymentMethodsRepository:
        """Репозиторий способов оплаты."""
