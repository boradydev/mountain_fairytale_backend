from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Query

from src.common.api.deps import Context
from src.common.api.excs_handlers import map_exceptions_to_responses
from src.common.api.schemas import StdResponse
from src.feat.audit_event.api.audit_schemas import AuditPageResp
from src.feat.audit_event.domain.audit_excs import InvalidAuditCursorException


events_router = APIRouter(prefix="/events", tags=["Журнал событий"])


@events_router.get(
    "",
    response_model=StdResponse[AuditPageResp],
    description="Аудит доступен всем сотрудникам. Сортировка createdAt DESC, eventId DESC. "
    "Курсоры привязаны к фильтрам. action фильтрует по действию; "
    "date_from включительно, date_to исключительно — время события с часовым поясом. "
    "after загружает новые события в порядке ASC; "
    "cursor и after несовместимы. latestCursor служит для проверки обновлений. "
    "nextCursor=null завершает страницу направления. Секреты и блокировки не записываются.",
    responses=map_exceptions_to_responses(InvalidAuditCursorException),
)
async def get_events(
    ctx: Context,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(max_length=2048)] = None,
    search: Annotated[str | None, Query(max_length=500)] = None,
    after: Annotated[str | None, Query(max_length=2048)] = None,
    action: Literal[
        "created",
        "updated",
        "activated",
        "deactivated",
        "cancelled",
        "restored",
        "deleted",
        "password_changed",
        "login",
        "other",
    ]
    | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> StdResponse[AuditPageResp]:
    page = await ctx.audit_use_cases.get_events().execute(
        search=search,
        cursor=cursor,
        limit=limit,
        after=after,
        action=action,
        date_from=date_from,
        date_to=date_to,
    )
    return StdResponse(limit=limit, data=AuditPageResp.model_validate(page))
