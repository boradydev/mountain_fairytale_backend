from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from src.common.api.deps import Context
from src.common.api.schemas import BaseSchema, StdResponse


class DashboardUpdatesResp(BaseSchema):
    server_id: UUID
    version: int
    clients_changed: bool
    delivery_days_changed: bool
    reload_required: bool


dashboard_updates_router = APIRouter(prefix="/dashboard-updates", tags=["Dashboard"])


@dashboard_updates_router.get(
    "",
    response_model=StdResponse[DashboardUpdatesResp],
    description="Long polling дашборда одного процесса: ожидание до 25 секунд без соединения с БД. "
    "Без позиции или при перезапуске сервера требуется обновление обоих списков. Журнал не затрагивается.",
)
async def get_dashboard_updates(
    ctx: Context,
    server_id: UUID | None = None,
    version: Annotated[int | None, Query(ge=0)] = None,
    timeout: Annotated[float, Query(ge=0, le=25)] = 25,
) -> StdResponse[DashboardUpdatesResp]:
    state = await ctx.dashboard_changes.wait(server_id=server_id, version=version, timeout=timeout)
    return StdResponse(data=DashboardUpdatesResp.model_validate(state, from_attributes=True))
