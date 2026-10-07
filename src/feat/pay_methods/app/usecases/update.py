from dataclasses import dataclass
from typing import Any
from uuid import UUID

from src.feat.pay_methods.app.abcs.pay_method_uow_abcs import IPaymentMethodsUOW
from src.feat.pay_methods.domain.pay_method_entities import PaymentMethod
from src.feat.pay_methods.domain.pay_method_excs import PaymentMethodNotFoundException


@dataclass(frozen=True, slots=True, kw_only=True)
class UpdatePaymentMethodDTO:
    actor_id: UUID
    payment_method_id: UUID
    payload: dict[str, Any]


class UpdatePaymentMethodUseCase:
    def __init__(
        self,
        uow: IPaymentMethodsUOW,
    ) -> None:
        self._uow = uow

    async def execute(
        self,
        dto: UpdatePaymentMethodDTO,
    ) -> PaymentMethod:
        async with self._uow as uow:
            payment_method = await uow.payment_methods.get_by_id(dto.payment_method_id)

            if payment_method is None:
                raise PaymentMethodNotFoundException()

            payment_method.update(
                actor_id=dto.actor_id,
                **dto.payload,
            )

            await uow.payment_methods.update(payment_method)

            await uow.commit(
                events=payment_method.pull_events(),
            )

            return payment_method
