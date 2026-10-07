from dataclasses import dataclass
from typing import Any
from uuid import UUID

from src.feat.products.app.abcs.product_uow_abcs import IProductsUOW
from src.feat.products.domain.product_entities import Product
from src.feat.products.domain.product_excs import ProductNotFoundException


@dataclass(frozen=True, slots=True, kw_only=True)
class UpdateProductDTO:
    actor_id: UUID
    product_id: UUID
    payload: dict[str, Any]


class UpdateProductUseCase:
    def __init__(
        self,
        uow: IProductsUOW,
    ) -> None:
        self._uow = uow

    async def execute(
        self,
        dto: UpdateProductDTO,
    ) -> Product:
        async with self._uow as uow:
            product = await uow.products.get_by_id(dto.product_id)

            if product is None:
                raise ProductNotFoundException(
                    product_id=dto.product_id,
                )

            product.update(
                actor_id=dto.actor_id,
                **dto.payload,
            )

            await uow.products.update(product)

            await uow.commit(
                events=product.pull_events(),
            )

            return product
