from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.common.app.abcs.uow_abcs import CommittedEventsHandler
from src.common.infra.db.postgres.common import IPostgresUOW
from src.common.infra.services.event_pud_service import EventPublisher
from src.feat.pay_methods.app.abcs.pay_method_uow_abcs import IPaymentMethodsUOW
from src.feat.pay_methods.domain.abcs.pay_method_repo_abcs import IPaymentMethodsRepository
from src.feat.pay_methods.infra.pay_method_repos import PaymentMethodsRepository


class PaymentMethodsUOW(IPostgresUOW, IPaymentMethodsUOW):
    _payment_methods: IPaymentMethodsRepository

    @property
    def payment_methods(self) -> IPaymentMethodsRepository:
        return self._payment_methods

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        on_committed: CommittedEventsHandler | None,
    ) -> None:
        self._session_factory = session_factory
        self._on_committed = on_committed

    async def __aenter__(self) -> Self:
        self._session = self._session_factory()
        self._event_publisher = EventPublisher(
            session=self._session,
        )

        self._payment_methods = PaymentMethodsRepository(
            session=self._session,
        )

        return self
