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
from src.api.fastapi.drivers.driver_schemas import (
    DriverResp,
    DriversResp,
    CreateDriverReq,
    UpdateDriverReq,
)
from src.domain.drivers import driver_excs


drivers_router = APIRouter(
    prefix="/drivers",
    tags=["Водители"],
)


@drivers_router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[DriversResp],
    responses=map_exceptions_to_responses(UnauthorizedException),
)
async def get_drivers(
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
    include_deactivated: Annotated[bool, Query()] = False,
) -> StdResponse[DriversResp]:
    pass


@drivers_router.get(
    "/{driver_id:uuid}",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[DriverResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        driver_excs.DriverNotFoundException,
    ),
)
async def get_driver(
    driver_id: UUID,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[DriverResp]:
    pass


@drivers_router.post(
    "/create",
    status_code=status.HTTP_201_CREATED,
    response_model=StdResponse[DriverResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        driver_excs.DriverDomainUpdateException,
    ),
)
async def create_driver(
    body: CreateDriverReq,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[DriverResp]:
    pass


@drivers_router.patch(
    "/{driver_id:uuid}",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[DriverResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        driver_excs.DriverNotFoundException,
        driver_excs.DriverDomainUpdateException,
    ),
)
async def update_driver(
    driver_id: UUID,
    body: UpdateDriverReq,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[DriverResp]:
    pass


@drivers_router.get(
    "/check-duplicate",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[DriverResp | NoneType],
    responses=map_exceptions_to_responses(UnauthorizedException),
    description="""
    Поиск дубликата водителя.
    Порог similarity: name >= 0.35.
    """,
)
async def check_duplicate_driver(
    name: Annotated[str, Query(min_length=1, max_length=120)],
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[DriverResp | None]:
    pass
