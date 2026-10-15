from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from src.common.api.api_excs import UnauthorizedException
from src.common.api.deps import AccessTokenPayloadDep, Context
from src.common.api.excs_handlers import map_exceptions_to_responses
from src.common.api.schemas import StdResponse
from src.feat.commissions.api.commission_schemas import (
    AssignRepresentativeReq,
    AssignRepresentativeResp,
    MonthlyCommissionsResp,
    RepresentativeDetailsResp,
)
from src.feat.commissions.domain.commission_excs import InactiveCommissionTargetException, SameCommissionTargetException
from src.feat.sales_rep.domain.sales_rep_excs import SalesRepresentativeNotFoundException


commissions_router = APIRouter(tags=["Commissions"])
Year = Annotated[int, Query(ge=1, le=9998)]
Month = Annotated[int, Query(ge=1, le=12)]


@commissions_router.get(
    "/commissions",
    response_model=StdResponse[MonthlyCommissionsResp],
    responses=map_exceptions_to_responses(UnauthorizedException),
)
async def get_monthly_commissions(ctx: Context, year: Year, month: Month, include_deactivated: bool = False):
    """Monthly exact accruals from saved snapshots; inactive filter only changes representative visibility."""
    report = await ctx.commissions_use_cases.get_report().execute(
        year=year, month=month, include_deactivated=include_deactivated
    )
    return StdResponse(data=report)


@commissions_router.get(
    "/commissions/sales-representatives/{sales_representative_id}",
    response_model=StdResponse[RepresentativeDetailsResp],
    responses=map_exceptions_to_responses(UnauthorizedException, SalesRepresentativeNotFoundException),
)
async def get_representative_commissions(ctx: Context, sales_representative_id: UUID, year: Year, month: Month):
    """Current assigned clients plus historical clients for the selected month, with actual rate breakdowns."""
    report = await ctx.commissions_use_cases.get_report().execute(
        year=year, month=month, representative_id=sales_representative_id
    )
    return StdResponse(data=report)


@commissions_router.put(
    "/sales-representatives/{sales_representative_id}/clients/assignment",
    response_model=StdResponse[AssignRepresentativeResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        SalesRepresentativeNotFoundException,
        InactiveCommissionTargetException,
        SameCommissionTargetException,
    ),
)
async def assign_representative_clients(
    ctx: Context, token: AccessTokenPayloadDep, sales_representative_id: UUID, body: AssignRepresentativeReq
):
    """Atomically reassign all current clients, including inactive clients; null clears assignment."""
    result = await ctx.commissions_use_cases.assign_clients().execute(
        actor_id=UUID(token.employee_id),
        source_id=sales_representative_id,
        target_id=body.target_sales_representative_id,
    )
    return StdResponse(data=result)
