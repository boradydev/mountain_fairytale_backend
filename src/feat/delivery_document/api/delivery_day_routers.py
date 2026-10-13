from datetime import date
from typing import Annotated

from fastapi import APIRouter, Path, Query, status

from src.common.api.api_excs import UnauthorizedException
from src.common.api.deps import AccessTokenPayloadDep, Context
from src.common.api.excs_handlers import map_exceptions_to_responses
from src.common.api.schemas import StdResponse
from src.feat.delivery_document.api.delivery_day_schemas import (
    DayDocumentsResp,
    DeliveryDayResp,
    DeliveryDaysResp,
)
from src.feat.delivery_document.app.usecases.get_day_documents import GetDayDocumentsDTO
from src.feat.delivery_document.app.usecases.get_days import GetDeliveryDaysDTO


delivery_days_router = APIRouter(prefix="/delivery-days", tags=["Delivery days"])


@delivery_days_router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[DeliveryDaysResp],
    responses=map_exceptions_to_responses(UnauthorizedException),
    description="Calendar days including empty dates, newest first; aggregates include active documents only.",
)
async def get_delivery_days(
    ctx: Context,
    _access_token_payload: AccessTokenPayloadDep,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1)] = 100,
) -> StdResponse[DeliveryDaysResp]:
    days, total = await ctx.delivery_documents_use_cases.get_delivery_days().execute(
        GetDeliveryDaysDTO(offset=offset, limit=limit)
    )
    return StdResponse(
        data=DeliveryDaysResp(delivery_days=[DeliveryDayResp.model_validate(day) for day in days]),
        offset=offset,
        limit=limit,
        total=total,
    )


@delivery_days_router.get(
    "/{planned_date}/documents",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[DayDocumentsResp],
    responses=map_exceptions_to_responses(UnauthorizedException),
    description="All delivery and pickup documents for the date, active first; no pagination or edit locks.",
)
async def get_day_documents(
    planned_date: Annotated[date, Path()],
    ctx: Context,
    _access_token_payload: AccessTokenPayloadDep,
    include_cancelled: Annotated[bool, Query()] = False,
) -> StdResponse[DayDocumentsResp]:
    documents = await ctx.delivery_documents_use_cases.get_day_documents().execute(
        GetDayDocumentsDTO(planned_date=planned_date, include_cancelled=include_cancelled)
    )
    return StdResponse(data=DayDocumentsResp.model_validate({"documents": documents}), total=len(documents))
