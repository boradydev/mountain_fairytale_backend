from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from src.common.api.deps import AccessTokenPayloadDep, Context
from src.common.api.schemas import StdResponse
from src.feat.delivery_document.api.sales_report_schemas import SalesReportResp
from src.feat.delivery_document.app.usecases.get_sales_report import GetSalesReportDTO


sales_report_router = APIRouter(prefix="/sales-report", tags=["Sales report"])


@sales_report_router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[SalesReportResp],
    description=(
        "Aggregated turnover for active delivery and pickup documents in an inclusive planned-date range, "
        "grouped by saved point payment method."
    ),
)
async def get_sales_report(
    ctx: Context,
    _access_token_payload: AccessTokenPayloadDep,
    date_from: Annotated[date, Query()],
    date_to: Annotated[date, Query()],
) -> StdResponse[SalesReportResp]:
    if date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from must be on or before date_to.")
    report = await ctx.delivery_documents_use_cases.get_sales_report().execute(
        GetSalesReportDTO(date_from=date_from, date_to=date_to),
    )
    return StdResponse(data=SalesReportResp.model_validate(report))
