from dataclasses import dataclass
from uuid import UUID

from src.app.payment_methods.abcs.uow import IPaymentMethodsUOW
from src.domain.payment_methods.payment_method_entities import PaymentMethod
from src.domain.payment_methods.payment_method_excs import PaymentMethodNotFoundException


@dataclass(frozen=True, slots=True, kw_only=True)
class GetPaymentMethodDTO:
    payment_method_id: UUID


class GetPaymentMethodUseCase:
    def __init__(
        self,
        uow: IPaymentMethodsUOW,
    ) -> None:
        self._uow = uow

    async def execute(
        self,
        dto: GetPaymentMethodDTO,
    ) -> PaymentMethod:
        async with self._uow as uow:
            payment_method = await uow.payment_methods.get_by_id(dto.payment_method_id)

            if payment_method is None:
                raise PaymentMethodNotFoundException()

            return payment_method
