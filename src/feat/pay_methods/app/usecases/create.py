from dataclasses import dataclass
from uuid import UUID

from src.feat.pay_methods.app.abcs.pay_method_uow_abcs import IPaymentMethodsUOW
from src.domain.pay_methods.payment_method_entities import PaymentMethod


@dataclass(frozen=True, slots=True, kw_only=True)
class CreatePaymentMethodDTO:
    actor_id: UUID
    name: str


class CreatePaymentMethodUseCase:
    def __init__(
        self,
        uow: IPaymentMethodsUOW,
    ) -> None:
        self._uow = uow

    async def execute(
        self,
        dto: CreatePaymentMethodDTO,
    ) -> PaymentMethod:
        async with self._uow as uow:
            payment_method = PaymentMethod.create(
                actor_id=dto.actor_id,
                name=dto.name,
            )

            await uow.payment_methods.add(payment_method)

            await uow.commit(
                events=payment_method.pull_events(),
            )

            return payment_method
