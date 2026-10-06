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
from src.api.fastapi.sales_representatives.sales_representative_schemas import (
    SalesRepresentativeResp,
    SalesRepresentativesResp,
    CreateSalesRepresentativeReq,
    UpdateSalesRepresentativeReq,
)
from src.domain.sales_representatives import sales_representative_excs


sales_representatives_router = APIRouter(
    prefix="/sales-representatives",
    tags=["Торговые представители"],
)


@sales_representatives_router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[SalesRepresentativesResp],
    responses=map_exceptions_to_responses(UnauthorizedException),
)
async def get_sales_representatives(
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
    include_deactivated: Annotated[bool, Query()] = False,
) -> StdResponse[SalesRepresentativesResp]:
    pass


@sales_representatives_router.get(
    "/{sales_representative_id:uuid}",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[SalesRepresentativeResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        sales_representative_excs.SalesRepresentativeNotFoundException,
    ),
)
async def get_sales_representative(
    sales_representative_id: UUID,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[SalesRepresentativeResp]:
    pass


@sales_representatives_router.post(
    "/create",
    status_code=status.HTTP_201_CREATED,
    response_model=StdResponse[SalesRepresentativeResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        sales_representative_excs.SalesRepresentativePhoneAlreadyExistsException,
        sales_representative_excs.SalesRepresentativeDomainUpdateException,
    ),
)
async def create_sales_representative(
    body: CreateSalesRepresentativeReq,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[SalesRepresentativeResp]:
    pass


@sales_representatives_router.patch(
    "/{sales_representative_id:uuid}",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[SalesRepresentativeResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        sales_representative_excs.SalesRepresentativeNotFoundException,
        sales_representative_excs.SalesRepresentativePhoneAlreadyExistsException,
        sales_representative_excs.SalesRepresentativeDomainUpdateException,
    ),
)
async def update_sales_representative(
    sales_representative_id: UUID,
    body: UpdateSalesRepresentativeReq,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[SalesRepresentativeResp]:
    pass


@sales_representatives_router.get(
    "/check-duplicate",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[SalesRepresentativeResp | NoneType],
    responses=map_exceptions_to_responses(UnauthorizedException),
    description="""
    Поиск дубликата торгового представителя.
    Требуется передать оба поля: name и phone.
    Пороги similarity: name >= 0.35, phone >= 0.50.
    """,
)
async def check_duplicate_sales_representative(
    name: Annotated[str, Query(min_length=1, max_length=120)],
    phone: Annotated[str, Query(min_length=1, max_length=32)],
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[SalesRepresentativeResp | None]:
    pass
