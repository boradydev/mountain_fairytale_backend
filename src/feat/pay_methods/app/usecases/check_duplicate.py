from dataclasses import dataclass

from src.feat.pay_methods.app.abcs.pay_method_uow_abcs import IPaymentMethodsUOW
from src.domain.pay_methods.payment_method_entities import PaymentMethod


@dataclass(frozen=True, slots=True, kw_only=True)
class CheckPaymentMethodDuplicateDTO:
    name: str


class CheckPaymentMethodDuplicateUseCase:
    def __init__(
        self,
        uow: IPaymentMethodsUOW,
    ) -> None:
        self._uow = uow

    async def execute(
        self,
        dto: CheckPaymentMethodDuplicateDTO,
    ) -> PaymentMethod | None:
        async with self._uow as uow:
            return await uow.payment_methods.search_by_fuzzy(
                dto.name,
            )
