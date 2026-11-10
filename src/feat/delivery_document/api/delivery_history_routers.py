from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query

from src.common.api.deps import AccessTokenPayloadDep, Context
from src.common.api.schemas import StdResponse
from src.feat.delivery_document.api.delivery_history_schemas import (
    ClientDeliveryHistoryResp,
    ClientDeliveryResp,
    DeliveryHistoryResp,
    HistoryDocumentResp,
)
from src.feat.delivery_document.app.usecases.get_history import GetDeliveryHistoryDTO
from src.feat.delivery_document.domain.delivery_history_models import validate_history_period


delivery_history_router = APIRouter(prefix="/delivery-history", tags=["Delivery history"])


@delivery_history_router.get("", response_model=StdResponse[DeliveryHistoryResp])
async def get_delivery_history(
    ctx: Context,
    _access_token_payload: AccessTokenPayloadDep,
    date_from: Annotated[date, Query()],
    date_to: Annotated[date, Query()],
    search: Annotated[str, Query(max_length=500)] = "",
    include_cancelled: bool = False,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    document_type: Literal["all", "delivery_route_sheet", "pickup_sheet"] = "all",
) -> StdResponse[DeliveryHistoryResp]:
    """Document history; client matches filter documents, never their overall totals."""
    try:
        validate_history_period(date_from, date_to)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    documents, total = await ctx.delivery_documents_use_cases.get_history().execute(
        GetDeliveryHistoryDTO(
            date_from=date_from,
            date_to=date_to,
            search=search,
            include_cancelled=include_cancelled,
            offset=offset,
            limit=limit,
            document_type=document_type,
        )
    )
    return StdResponse(
        data=DeliveryHistoryResp(documents=[HistoryDocumentResp.model_validate(doc) for doc in documents]),
        total=total,
        offset=offset,
        limit=limit,
    )


client_delivery_history_router = APIRouter(prefix="/client-delivery-history", tags=["Delivery history"])


@client_delivery_history_router.get("", response_model=StdResponse[ClientDeliveryHistoryResp])
async def get_client_delivery_history(
    ctx: Context,
    _access_token_payload: AccessTokenPayloadDep,
    date_from: Annotated[date, Query()],
    date_to: Annotated[date, Query()],
    search: Annotated[str, Query(max_length=500)] = "",
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> StdResponse[ClientDeliveryHistoryResp]:
    try:
        validate_history_period(date_from, date_to)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    deliveries, total = await ctx.delivery_documents_use_cases.get_history().execute(
        GetDeliveryHistoryDTO(
            date_from=date_from, date_to=date_to, search=search, offset=offset, limit=limit, clients=True
        )
    )
    return StdResponse(
        data=ClientDeliveryHistoryResp(deliveries=[ClientDeliveryResp.model_validate(point) for point in deliveries]),
        total=total,
        offset=offset,
        limit=limit,
    )
