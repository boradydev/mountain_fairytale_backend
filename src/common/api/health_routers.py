import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from src.common.api.schemas import BaseSchema, StdResponse
from src.common.infra.db.postgres.database import Postgres
from src.core.build_info import APP_COMMIT_SHA, APP_VERSION


logger = logging.getLogger(__name__)
health_router = APIRouter(prefix="/health", tags=["Эксплуатация"])


class HealthStatus(BaseSchema):
    status: str
    version: str = APP_VERSION
    commit_sha: str = APP_COMMIT_SHA


def get_health_database(request: Request) -> Postgres:
    return request.app.state.postgres


@health_router.get("/live", response_model=StdResponse[HealthStatus])
async def live() -> StdResponse[HealthStatus]:
    return StdResponse(data=HealthStatus(status="alive"))


@health_router.get(
    "/ready",
    response_model=StdResponse[HealthStatus],
    responses={503: {"description": "Database is unavailable"}},
)
async def ready(database: Annotated[Postgres, Depends(get_health_database)]):
    try:
        await asyncio.wait_for(database.check_connection(), timeout=3)
    except (SQLAlchemyError, OSError, TimeoutError):
        logger.warning("Database readiness check failed")
        return JSONResponse(
            status_code=503,
            content=StdResponse(data=HealthStatus(status="unavailable")).model_dump(mode="json", by_alias=True),
        )
    return StdResponse(data=HealthStatus(status="ready"))
