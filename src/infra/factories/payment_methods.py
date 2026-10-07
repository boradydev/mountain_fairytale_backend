from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.payment_methods.usecases.check_duplicate import CheckPaymentMethodDuplicateUseCase
from src.app.payment_methods.usecases.create import CreatePaymentMethodUseCase
from src.app.payment_methods.usecases.get import GetPaymentMethodUseCase
from src.app.payment_methods.usecases.get_all import GetPaymentMethodsUseCase
from src.app.payment_methods.usecases.update import UpdatePaymentMethodUseCase
from src.infra.db.postgres.uow.payment_methods import PaymentMethodsUOW


class PaymentMethodsUseCaseFactory:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._session_factory = session_factory

    def create_payment_method(self) -> CreatePaymentMethodUseCase:
        return CreatePaymentMethodUseCase(
            uow=self._create_uow(),
        )

    def get_payment_method(self) -> GetPaymentMethodUseCase:
        return GetPaymentMethodUseCase(
            uow=self._create_uow(),
        )

    def get_payment_methods(self) -> GetPaymentMethodsUseCase:
        return GetPaymentMethodsUseCase(
            uow=self._create_uow(),
        )

    def update_payment_method(self) -> UpdatePaymentMethodUseCase:
        return UpdatePaymentMethodUseCase(
            uow=self._create_uow(),
        )

    def check_duplicate(self) -> CheckPaymentMethodDuplicateUseCase:
        return CheckPaymentMethodDuplicateUseCase(
            uow=self._create_uow(),
        )

    def _create_uow(self) -> PaymentMethodsUOW:
        return PaymentMethodsUOW(
            session_factory=self._session_factory,
        )

    @property
    def create_uow(self) -> PaymentMethodsUOW:
        return self._create_uow()
