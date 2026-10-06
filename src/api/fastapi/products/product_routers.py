from types import NoneType
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from src.api.fastapi.common.api_excs import UnauthorizedException
from src.api.fastapi.common.deps import (
    AccessTokenPayloadDep,
    Context,
)
from src.api.fastapi.common.excs_handlers import map_exceptions_to_responses
from src.api.fastapi.common.schemas import StdResponse
from src.api.fastapi.products.product_schemas import (
    ProductResp,
    ProductsResp,
    CreateProductReq,
    UpdateProductReq,
)
from src.domain.products import product_excs


products_router = APIRouter(
    prefix="/products",
    tags=["Товары"],
)


@products_router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[ProductsResp],
    responses=map_exceptions_to_responses(UnauthorizedException),
)
async def get_products(
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
    include_deactivated: Annotated[bool, Query()] = False,
) -> StdResponse[ProductsResp]:
    pass


@products_router.get(
    "/{product_id:uuid}",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[ProductResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        product_excs.ProductNotFoundException,
    ),
)
async def get_product(
    product_id: UUID,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[ProductResp]:
    pass


@products_router.post(
    "/create",
    status_code=status.HTTP_201_CREATED,
    response_model=StdResponse[ProductResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        product_excs.ProductNameAlreadyExistsException,
        product_excs.ProductDomainUpdateException,
    ),
)
async def create_product(
    body: CreateProductReq,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[ProductResp]:
    pass


@products_router.patch(
    "/{product_id:uuid}",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[ProductResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        product_excs.ProductNotFoundException,
        product_excs.ProductNameAlreadyExistsException,
        product_excs.ProductDomainUpdateException,
    ),
)
async def update_product(
    product_id: UUID,
    body: UpdateProductReq,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[ProductResp]:
    pass


@products_router.get(
    "/check-duplicate",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[ProductResp | NoneType],
    responses=map_exceptions_to_responses(UnauthorizedException),
    description="""
    Поиск дубликата товара.
    Порог similarity: name >= 0.35.
    """,
)
async def check_duplicate_product(
    name: Annotated[str, Query(min_length=1, max_length=120)],
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[ProductResp | None]:
    pass
