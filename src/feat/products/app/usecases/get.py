from dataclasses import dataclass
from uuid import UUID

from src.feat.products.app.abcs.product_uow_abcs import IProductsUOW
from src.feat.products.domain.product_entities import Product
from src.feat.products.domain.product_excs import ProductNotFoundException


@dataclass(frozen=True, slots=True, kw_only=True)
class GetProductDTO:
    product_id: UUID


class GetProductUseCase:
    def __init__(
        self,
        uow: IProductsUOW,
    ) -> None:
        self._uow = uow

    async def execute(
        self,
        dto: GetProductDTO,
    ) -> Product:
        async with self._uow as uow:
            product = await uow.products.get_by_id(dto.product_id)

            if product is None:
                raise ProductNotFoundException(
                    product_id=dto.product_id,
                )

            return product
