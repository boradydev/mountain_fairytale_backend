from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import Field

from src.common.api.patch_schema import BasePatchSchema
from src.common.api.schemas import BaseSchema
from src.feat.products.domain.product_entities import Product


class ProductResp(BaseSchema):
    product_id: UUID
    name: str
    base_price: float
    created_at: datetime
    is_active: bool


class ProductsResp(BaseSchema):
    products: list[ProductResp]


class CreateProductReq(BaseSchema):
    name: Annotated[str, Field(min_length=1, max_length=120)]
    base_price: Annotated[float, Field(ge=0, le=1_000_000_000)]


class UpdateProductReq(BasePatchSchema):
    __entity__ = Product

    name: str | None = Field(default=None, min_length=1, max_length=120)
    base_price: float | None = Field(default=None, ge=0, le=1_000_000_000)
    is_active: bool | None = None
