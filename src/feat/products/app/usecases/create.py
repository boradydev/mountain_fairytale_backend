from dataclasses import dataclass
from uuid import UUID

from src.feat.products.app.abcs.product_uow_abcs import IProductsUOW
from src.feat.products.domain.product_entities import Product


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateProductDTO:
    actor_id: UUID
    name: str
    base_price: float


class CreateProductUseCase:
    def __init__(
        self,
        uow: IProductsUOW,
    ) -> None:
        self._uow = uow

    async def execute(
        self,
        dto: CreateProductDTO,
    ) -> Product:
        async with self._uow as uow:
            product = Product.create(
                actor_id=dto.actor_id,
                name=dto.name,
                base_price=dto.base_price,
            )

            await uow.products.add(product)

            await uow.commit(
                events=product.pull_events(),
            )

            return product
