from dataclasses import dataclass

from src.feat.pay_methods.app.abcs.pay_method_uow_abcs import IPaymentMethodsUOW
from src.domain.pay_methods.payment_method_entities import PaymentMethod


@dataclass(frozen=True, slots=True, kw_only=True)
class GetPaymentMethodsDTO:
    include_deactivated: bool


class GetPaymentMethodsUseCase:
    def __init__(
        self,
        uow: IPaymentMethodsUOW,
    ) -> None:
        self._uow = uow

    async def execute(
        self,
        dto: GetPaymentMethodsDTO,
    ) -> list[PaymentMethod]:
        async with self._uow as uow:
            return await uow.payment_methods.get_all(
                include_deactivated=dto.include_deactivated,
            )
