from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path, Query, status

from src.common.api.api_excs import UnauthorizedException
from src.common.api.deps import AccessTokenPayloadDep, Context
from src.common.api.excs_handlers import map_exceptions_to_responses
from src.common.api.schemas import StdResponse
from src.feat.delivery_document.api.delivery_document_schemas import (
    CreateDeliveryRouteSheetReq,
    CreatePickupSheetReq,
    DeliveryDocumentEditLockResp,
    DeliveryRouteSheetResp,
    DeliveryRouteSheetsResp,
    PickupSheetResp,
    PickupSheetsResp,
    UpdateDeliveryRouteSheetReq,
    UpdatePickupSheetReq,
)
from src.feat.delivery_document.domain import delivery_document_excs


delivery_route_sheets_router = APIRouter(
    prefix="/delivery-route-sheets",
    tags=["Маршрутные листы доставки"],
)

pickup_sheets_router = APIRouter(
    prefix="/pickup-sheets",
    tags=["Листы самовывоза"],
)


_DOCUMENT_EXCEPTIONS = (
    delivery_document_excs.DeliveryDocumentNotFoundException,
    delivery_document_excs.DeliveryDocumentUpdateException,
    delivery_document_excs.DeliveryDocumentRelatedEntityNotFoundException,
    delivery_document_excs.DeliveryDocumentPointClientAlreadyExistsException,
    delivery_document_excs.DeliveryDocumentPointProductAlreadyExistsException,
    delivery_document_excs.DeliveryDocumentLockedException,
    delivery_document_excs.DeliveryDocumentEditLockNotFoundException,
    delivery_document_excs.DeliveryDocumentEditLockNotOwnedException,
)


@delivery_route_sheets_router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[DeliveryRouteSheetsResp],
    responses=map_exceptions_to_responses(UnauthorizedException),
)
async def get_delivery_route_sheets(
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
    include_cancelled: Annotated[bool, Query()] = False,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1)] = 100,
) -> StdResponse[DeliveryRouteSheetsResp]:
    pass


@delivery_route_sheets_router.get(
    "/{delivery_document_id:uuid}",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[DeliveryRouteSheetResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        delivery_document_excs.DeliveryDocumentNotFoundException,
    ),
)
async def get_delivery_route_sheet(
    delivery_document_id: Annotated[UUID, Path()],
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[DeliveryRouteSheetResp]:
    pass


@delivery_route_sheets_router.post(
    "/create",
    status_code=status.HTTP_201_CREATED,
    response_model=StdResponse[DeliveryRouteSheetResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        delivery_document_excs.DeliveryDocumentUpdateException,
        delivery_document_excs.DeliveryDocumentRelatedEntityNotFoundException,
        delivery_document_excs.DeliveryDocumentPointClientAlreadyExistsException,
        delivery_document_excs.DeliveryDocumentPointProductAlreadyExistsException,
    ),
)
async def create_delivery_route_sheet(
    body: CreateDeliveryRouteSheetReq,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[DeliveryRouteSheetResp]:
    pass


@delivery_route_sheets_router.patch(
    "/{delivery_document_id:uuid}",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[DeliveryRouteSheetResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        *_DOCUMENT_EXCEPTIONS,
    ),
)
async def update_delivery_route_sheet(
    delivery_document_id: Annotated[UUID, Path()],
    body: UpdateDeliveryRouteSheetReq,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[DeliveryRouteSheetResp]:
    pass


@delivery_route_sheets_router.post(
    "/{delivery_document_id:uuid}/cancel",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[DeliveryRouteSheetResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        delivery_document_excs.DeliveryDocumentNotFoundException,
        delivery_document_excs.DeliveryDocumentLockedException,
        delivery_document_excs.DeliveryDocumentUpdateException,
    ),
)
async def cancel_delivery_route_sheet(
    delivery_document_id: Annotated[UUID, Path()],
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[DeliveryRouteSheetResp]:
    pass


@delivery_route_sheets_router.post(
    "/{delivery_document_id:uuid}/restore",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[DeliveryRouteSheetResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        delivery_document_excs.DeliveryDocumentNotFoundException,
        delivery_document_excs.DeliveryDocumentUpdateException,
    ),
)
async def restore_delivery_route_sheet(
    delivery_document_id: Annotated[UUID, Path()],
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[DeliveryRouteSheetResp]:
    pass


@delivery_route_sheets_router.post(
    "/{delivery_document_id:uuid}/edit-lock",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[DeliveryDocumentEditLockResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        delivery_document_excs.DeliveryDocumentNotFoundException,
        delivery_document_excs.DeliveryDocumentLockedException,
    ),
)
async def acquire_delivery_route_sheet_edit_lock(
    delivery_document_id: Annotated[UUID, Path()],
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[DeliveryDocumentEditLockResp]:
    pass


@delivery_route_sheets_router.patch(
    "/{delivery_document_id:uuid}/edit-lock",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[DeliveryDocumentEditLockResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        delivery_document_excs.DeliveryDocumentNotFoundException,
        delivery_document_excs.DeliveryDocumentEditLockNotFoundException,
        delivery_document_excs.DeliveryDocumentEditLockNotOwnedException,
    ),
)
async def renew_delivery_route_sheet_edit_lock(
    delivery_document_id: Annotated[UUID, Path()],
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[DeliveryDocumentEditLockResp]:
    pass


@delivery_route_sheets_router.delete(
    "/{delivery_document_id:uuid}/edit-lock",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[None],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        delivery_document_excs.DeliveryDocumentNotFoundException,
        delivery_document_excs.DeliveryDocumentEditLockNotFoundException,
        delivery_document_excs.DeliveryDocumentEditLockNotOwnedException,
    ),
)
async def release_delivery_route_sheet_edit_lock(
    delivery_document_id: Annotated[UUID, Path()],
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[None]:
    pass


@pickup_sheets_router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[PickupSheetsResp],
    responses=map_exceptions_to_responses(UnauthorizedException),
)
async def get_pickup_sheets(
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
    include_cancelled: Annotated[bool, Query()] = False,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1)] = 100,
) -> StdResponse[PickupSheetsResp]:
    pass


@pickup_sheets_router.get(
    "/{delivery_document_id:uuid}",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[PickupSheetResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        delivery_document_excs.DeliveryDocumentNotFoundException,
    ),
)
async def get_pickup_sheet(
    delivery_document_id: Annotated[UUID, Path()],
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[PickupSheetResp]:
    pass


@pickup_sheets_router.post(
    "/create",
    status_code=status.HTTP_201_CREATED,
    response_model=StdResponse[PickupSheetResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        delivery_document_excs.DeliveryDocumentUpdateException,
        delivery_document_excs.DeliveryDocumentRelatedEntityNotFoundException,
        delivery_document_excs.DeliveryDocumentPointClientAlreadyExistsException,
        delivery_document_excs.DeliveryDocumentPointProductAlreadyExistsException,
    ),
)
async def create_pickup_sheet(
    body: CreatePickupSheetReq,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[PickupSheetResp]:
    pass


@pickup_sheets_router.patch(
    "/{delivery_document_id:uuid}",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[PickupSheetResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        *_DOCUMENT_EXCEPTIONS,
    ),
)
async def update_pickup_sheet(
    delivery_document_id: Annotated[UUID, Path()],
    body: UpdatePickupSheetReq,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[PickupSheetResp]:
    pass


@pickup_sheets_router.post(
    "/{delivery_document_id:uuid}/cancel",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[PickupSheetResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        delivery_document_excs.DeliveryDocumentNotFoundException,
        delivery_document_excs.DeliveryDocumentLockedException,
        delivery_document_excs.DeliveryDocumentUpdateException,
    ),
)
async def cancel_pickup_sheet(
    delivery_document_id: Annotated[UUID, Path()],
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[PickupSheetResp]:
    pass


@pickup_sheets_router.post(
    "/{delivery_document_id:uuid}/restore",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[PickupSheetResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        delivery_document_excs.DeliveryDocumentNotFoundException,
        delivery_document_excs.DeliveryDocumentUpdateException,
    ),
)
async def restore_pickup_sheet(
    delivery_document_id: Annotated[UUID, Path()],
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[PickupSheetResp]:
    pass


@pickup_sheets_router.post(
    "/{delivery_document_id:uuid}/edit-lock",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[DeliveryDocumentEditLockResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        delivery_document_excs.DeliveryDocumentNotFoundException,
        delivery_document_excs.DeliveryDocumentLockedException,
    ),
)
async def acquire_pickup_sheet_edit_lock(
    delivery_document_id: Annotated[UUID, Path()],
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[DeliveryDocumentEditLockResp]:
    pass


@pickup_sheets_router.patch(
    "/{delivery_document_id:uuid}/edit-lock",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[DeliveryDocumentEditLockResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        delivery_document_excs.DeliveryDocumentNotFoundException,
        delivery_document_excs.DeliveryDocumentEditLockNotFoundException,
        delivery_document_excs.DeliveryDocumentEditLockNotOwnedException,
    ),
)
async def renew_pickup_sheet_edit_lock(
    delivery_document_id: Annotated[UUID, Path()],
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[DeliveryDocumentEditLockResp]:
    pass


@pickup_sheets_router.delete(
    "/{delivery_document_id:uuid}/edit-lock",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[None],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        delivery_document_excs.DeliveryDocumentNotFoundException,
        delivery_document_excs.DeliveryDocumentEditLockNotFoundException,
        delivery_document_excs.DeliveryDocumentEditLockNotOwnedException,
    ),
)
async def release_pickup_sheet_edit_lock(
    delivery_document_id: Annotated[UUID, Path()],
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[None]:
    pass
