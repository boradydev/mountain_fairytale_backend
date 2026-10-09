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
from src.feat.delivery_document.app.usecases.change_status import (
    ChangeDeliveryDocumentStatusDTO,
)
from src.feat.delivery_document.app.usecases.create import (
    CreateDeliveryDocumentDTO,
)
from src.feat.delivery_document.app.usecases.edit_lock import (
    DeliveryDocumentEditLockDTO,
)
from src.feat.delivery_document.app.usecases.get import GetDeliveryDocumentDTO
from src.feat.delivery_document.app.usecases.get_all import (
    GetDeliveryDocumentsDTO,
)
from src.feat.delivery_document.app.usecases.update import (
    UpdateDeliveryDocumentDTO,
)
from src.feat.delivery_document.domain import delivery_document_excs
from src.feat.delivery_document.domain.delivery_document_entities import (
    DeliveryDocument,
)


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


def _actor_id(access_token_payload: object) -> UUID:
    return UUID(access_token_payload.employee_id)  # type: ignore[attr-defined]


def _route_sheet_response(document: DeliveryDocument) -> DeliveryRouteSheetResp:
    return DeliveryRouteSheetResp.model_validate(document)


def _pickup_sheet_response(document: DeliveryDocument) -> PickupSheetResp:
    return PickupSheetResp.model_validate(document)


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
    documents, total = await ctx.delivery_documents_use_cases.get_delivery_documents().execute(
        GetDeliveryDocumentsDTO(
            document_type=DeliveryDocument.TYPE_DELIVERY_ROUTE_SHEET,
            include_cancelled=include_cancelled,
            offset=offset,
            limit=limit,
        ),
    )
    return StdResponse(
        data=DeliveryRouteSheetsResp(
            delivery_route_sheets=[
                _route_sheet_response(document) for document in documents
            ],
        ),
        offset=offset,
        limit=limit,
        total=total,
    )


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
    document = await ctx.delivery_documents_use_cases.get_delivery_document().execute(
        GetDeliveryDocumentDTO(
            delivery_document_id=delivery_document_id,
            document_type=DeliveryDocument.TYPE_DELIVERY_ROUTE_SHEET,
        ),
    )
    return StdResponse(data=_route_sheet_response(document))


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
    document = await ctx.delivery_documents_use_cases.create_delivery_document().execute(
        CreateDeliveryDocumentDTO(
            actor_id=_actor_id(access_token_payload),
            document_type=DeliveryDocument.TYPE_DELIVERY_ROUTE_SHEET,
            planned_date=body.planned_date,
            driver_id=body.driver_id,
            car_id=body.car_id,
            start_mileage=body.start_mileage,
            end_mileage=body.end_mileage,
            points=body.points,
        ),
    )
    return StdResponse(data=_route_sheet_response(document))


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
    document = await ctx.delivery_documents_use_cases.update_delivery_document().execute(
        UpdateDeliveryDocumentDTO(
            actor_id=_actor_id(access_token_payload),
            delivery_document_id=delivery_document_id,
            document_type=DeliveryDocument.TYPE_DELIVERY_ROUTE_SHEET,
            payload=body,
        ),
    )
    return StdResponse(data=_route_sheet_response(document))


@delivery_route_sheets_router.post(
    "/{delivery_document_id:uuid}/cancel",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[DeliveryRouteSheetResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        delivery_document_excs.DeliveryDocumentNotFoundException,
        delivery_document_excs.DeliveryDocumentLockedException,
        delivery_document_excs.DeliveryDocumentEditLockNotFoundException,
        delivery_document_excs.DeliveryDocumentUpdateException,
    ),
)
async def cancel_delivery_route_sheet(
    delivery_document_id: Annotated[UUID, Path()],
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[DeliveryRouteSheetResp]:
    document = await ctx.delivery_documents_use_cases.cancel_delivery_document().execute(
        ChangeDeliveryDocumentStatusDTO(
            actor_id=_actor_id(access_token_payload),
            delivery_document_id=delivery_document_id,
            document_type=DeliveryDocument.TYPE_DELIVERY_ROUTE_SHEET,
        ),
    )
    return StdResponse(data=_route_sheet_response(document))


@delivery_route_sheets_router.post(
    "/{delivery_document_id:uuid}/restore",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[DeliveryRouteSheetResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        delivery_document_excs.DeliveryDocumentNotFoundException,
        delivery_document_excs.DeliveryDocumentLockedException,
        delivery_document_excs.DeliveryDocumentUpdateException,
    ),
)
async def restore_delivery_route_sheet(
    delivery_document_id: Annotated[UUID, Path()],
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[DeliveryRouteSheetResp]:
    document = await ctx.delivery_documents_use_cases.restore_delivery_document().execute(
        ChangeDeliveryDocumentStatusDTO(
            actor_id=_actor_id(access_token_payload),
            delivery_document_id=delivery_document_id,
            document_type=DeliveryDocument.TYPE_DELIVERY_ROUTE_SHEET,
        ),
    )
    return StdResponse(data=_route_sheet_response(document))


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
    owner_name = await ctx.delivery_documents_use_cases.acquire_edit_lock().execute(
        DeliveryDocumentEditLockDTO(
            delivery_document_id=delivery_document_id,
            document_type=DeliveryDocument.TYPE_DELIVERY_ROUTE_SHEET,
            employee_id=_actor_id(access_token_payload),
        ),
    )
    return StdResponse(data=DeliveryDocumentEditLockResp(owner_name=owner_name))


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
    owner_name = await ctx.delivery_documents_use_cases.renew_edit_lock().execute(
        DeliveryDocumentEditLockDTO(
            delivery_document_id=delivery_document_id,
            document_type=DeliveryDocument.TYPE_DELIVERY_ROUTE_SHEET,
            employee_id=_actor_id(access_token_payload),
        ),
    )
    return StdResponse(data=DeliveryDocumentEditLockResp(owner_name=owner_name))


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
    await ctx.delivery_documents_use_cases.release_edit_lock().execute(
        DeliveryDocumentEditLockDTO(
            delivery_document_id=delivery_document_id,
            document_type=DeliveryDocument.TYPE_DELIVERY_ROUTE_SHEET,
            employee_id=_actor_id(access_token_payload),
        ),
    )
    return StdResponse(data=None)


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
    documents, total = await ctx.delivery_documents_use_cases.get_delivery_documents().execute(
        GetDeliveryDocumentsDTO(
            document_type=DeliveryDocument.TYPE_PICKUP_SHEET,
            include_cancelled=include_cancelled,
            offset=offset,
            limit=limit,
        ),
    )
    return StdResponse(
        data=PickupSheetsResp(
            pickup_sheets=[_pickup_sheet_response(document) for document in documents],
        ),
        offset=offset,
        limit=limit,
        total=total,
    )


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
    document = await ctx.delivery_documents_use_cases.get_delivery_document().execute(
        GetDeliveryDocumentDTO(
            delivery_document_id=delivery_document_id,
            document_type=DeliveryDocument.TYPE_PICKUP_SHEET,
        ),
    )
    return StdResponse(data=_pickup_sheet_response(document))


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
    document = await ctx.delivery_documents_use_cases.create_delivery_document().execute(
        CreateDeliveryDocumentDTO(
            actor_id=_actor_id(access_token_payload),
            document_type=DeliveryDocument.TYPE_PICKUP_SHEET,
            planned_date=body.planned_date,
            points=body.points,
        ),
    )
    return StdResponse(data=_pickup_sheet_response(document))


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
    document = await ctx.delivery_documents_use_cases.update_delivery_document().execute(
        UpdateDeliveryDocumentDTO(
            actor_id=_actor_id(access_token_payload),
            delivery_document_id=delivery_document_id,
            document_type=DeliveryDocument.TYPE_PICKUP_SHEET,
            payload=body,
        ),
    )
    return StdResponse(data=_pickup_sheet_response(document))


@pickup_sheets_router.post(
    "/{delivery_document_id:uuid}/cancel",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[PickupSheetResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        delivery_document_excs.DeliveryDocumentNotFoundException,
        delivery_document_excs.DeliveryDocumentLockedException,
        delivery_document_excs.DeliveryDocumentEditLockNotFoundException,
        delivery_document_excs.DeliveryDocumentUpdateException,
    ),
)
async def cancel_pickup_sheet(
    delivery_document_id: Annotated[UUID, Path()],
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[PickupSheetResp]:
    document = await ctx.delivery_documents_use_cases.cancel_delivery_document().execute(
        ChangeDeliveryDocumentStatusDTO(
            actor_id=_actor_id(access_token_payload),
            delivery_document_id=delivery_document_id,
            document_type=DeliveryDocument.TYPE_PICKUP_SHEET,
        ),
    )
    return StdResponse(data=_pickup_sheet_response(document))


@pickup_sheets_router.post(
    "/{delivery_document_id:uuid}/restore",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[PickupSheetResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        delivery_document_excs.DeliveryDocumentNotFoundException,
        delivery_document_excs.DeliveryDocumentLockedException,
        delivery_document_excs.DeliveryDocumentUpdateException,
    ),
)
async def restore_pickup_sheet(
    delivery_document_id: Annotated[UUID, Path()],
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[PickupSheetResp]:
    document = await ctx.delivery_documents_use_cases.restore_delivery_document().execute(
        ChangeDeliveryDocumentStatusDTO(
            actor_id=_actor_id(access_token_payload),
            delivery_document_id=delivery_document_id,
            document_type=DeliveryDocument.TYPE_PICKUP_SHEET,
        ),
    )
    return StdResponse(data=_pickup_sheet_response(document))


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
    owner_name = await ctx.delivery_documents_use_cases.acquire_edit_lock().execute(
        DeliveryDocumentEditLockDTO(
            delivery_document_id=delivery_document_id,
            document_type=DeliveryDocument.TYPE_PICKUP_SHEET,
            employee_id=_actor_id(access_token_payload),
        ),
    )
    return StdResponse(data=DeliveryDocumentEditLockResp(owner_name=owner_name))


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
    owner_name = await ctx.delivery_documents_use_cases.renew_edit_lock().execute(
        DeliveryDocumentEditLockDTO(
            delivery_document_id=delivery_document_id,
            document_type=DeliveryDocument.TYPE_PICKUP_SHEET,
            employee_id=_actor_id(access_token_payload),
        ),
    )
    return StdResponse(data=DeliveryDocumentEditLockResp(owner_name=owner_name))


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
    await ctx.delivery_documents_use_cases.release_edit_lock().execute(
        DeliveryDocumentEditLockDTO(
            delivery_document_id=delivery_document_id,
            document_type=DeliveryDocument.TYPE_PICKUP_SHEET,
            employee_id=_actor_id(access_token_payload),
        ),
    )
    return StdResponse(data=None)
