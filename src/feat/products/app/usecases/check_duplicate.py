from dataclasses import dataclass

from src.feat.products.app.abcs.product_uow_abcs import IProductsUOW
from src.feat.products.domain.product_entities import Product


@dataclass(frozen=True, slots=True, kw_only=True)
class CheckProductDuplicateDTO:
    name: str


class CheckProductDuplicateUseCase:
    def __init__(
        self,
        uow: IProductsUOW,
    ) -> None:
        self._uow = uow

    async def execute(
        self,
        dto: CheckProductDuplicateDTO,
    ) -> Product | None:
        async with self._uow as uow:
            return await uow.products.search_by_fuzzy(
                dto.name,
            )
