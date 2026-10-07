from dataclasses import dataclass

from src.app.payment_methods.abcs.uow import IPaymentMethodsUOW
from src.domain.payment_methods.payment_method_entities import PaymentMethod


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
