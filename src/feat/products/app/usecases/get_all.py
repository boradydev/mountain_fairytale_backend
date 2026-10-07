from dataclasses import dataclass

from src.feat.products.app.abcs.product_uow_abcs import IProductsUOW
from src.domain.products.product_entities import Product


@dataclass(frozen=True, slots=True, kw_only=True)
class GetProductsDTO:
    include_deactivated: bool


class GetProductsUseCase:
    def __init__(
        self,
        uow: IProductsUOW,
    ) -> None:
        self._uow = uow

    async def execute(
        self,
        dto: GetProductsDTO,
    ) -> list[Product]:
        async with self._uow as uow:
            return await uow.products.get_all(
                include_deactivated=dto.include_deactivated,
            )
