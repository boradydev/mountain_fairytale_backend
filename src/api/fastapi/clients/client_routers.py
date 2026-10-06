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
from src.api.fastapi.clients.client_schemas import (
    ClientResp,
    ClientsResp,
    CreateClientReq,
    UpdateClientReq,
)
from src.domain.clients import client_excs


clients_router = APIRouter(
    prefix="/clients",
    tags=["Клиенты"],
)


@clients_router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[ClientsResp],
    responses=map_exceptions_to_responses(UnauthorizedException),
    description="""
    Получение списка клиентов с пагинацией.
    
    Query parameters:
        include_deactivated: если true, вернуть всех клиентов.
        offset: смещение (default 0, ge=0).
        limit: количество записей (default 100, ge=1).
    """,
)
async def get_clients(
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
    include_deactivated: Annotated[bool, Query()] = False,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1)] = 100,
) -> StdResponse[ClientsResp]:
    pass


@clients_router.get(
    "/{client_id:uuid}",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[ClientResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        client_excs.ClientNotFoundException,
    ),
)
async def get_client(
    client_id: UUID,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[ClientResp]:
    pass


@clients_router.post(
    "/create",
    status_code=status.HTTP_201_CREATED,
    response_model=StdResponse[ClientResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        client_excs.ClientDomainUpdateException,
    ),
)
async def create_client(
    body: CreateClientReq,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[ClientResp]:
    pass


@clients_router.patch(
    "/{client_id:uuid}",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[ClientResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        client_excs.ClientNotFoundException,
        client_excs.ClientDomainUpdateException,
    ),
)
async def update_client(
    client_id: UUID,
    body: UpdateClientReq,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[ClientResp]:
    pass


@clients_router.get(
    "/check-duplicate",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[ClientResp | NoneType],
    responses=map_exceptions_to_responses(UnauthorizedException),
    description="""
    Поиск дубликата клиента.
    Требуется передать минимум два поля из: name, phone, address.
    Пороги similarity: name >= 0.35, phone >= 0.50, address >= 0.25.
    """,
)
async def check_duplicate_client(
    name: Annotated[str | None, Query()] = None,
    phone: Annotated[str | None, Query()] = None,
    address: Annotated[str | None, Query()] = None,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[ClientResp | None]:
    pass
