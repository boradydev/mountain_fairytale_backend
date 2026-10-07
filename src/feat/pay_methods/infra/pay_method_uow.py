from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.feat.pay_methods.app.abcs.pay_method_uow_abcs import IPaymentMethodsUOW
from src.domain.pay_methods.abcs.payment_methods_repo_abcs import IPaymentMethodsRepository
from src.feat.pay_methods.infra.pay_method_repos import PaymentMethodsRepository
from src.infra.db.postgres.uow.common import IPostgresUOW
from src.infra.services.event_publisher.service import EventPublisher


class PaymentMethodsUOW(IPostgresUOW, IPaymentMethodsUOW):
    _payment_methods: IPaymentMethodsRepository

    @property
    def payment_methods(self) -> IPaymentMethodsRepository:
        return self._payment_methods

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._session_factory = session_factory

    async def __aenter__(self) -> Self:
        self._session = self._session_factory()
        self._event_publisher = EventPublisher(
            session=self._session,
        )

        self._payment_methods = PaymentMethodsRepository(
            session=self._session,
        )

        return self
