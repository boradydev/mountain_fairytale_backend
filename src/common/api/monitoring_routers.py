import os
import re

from fastapi import APIRouter

from src.common.api.schemas import BaseSchema, StdResponse


monitoring_router = APIRouter(prefix="/monitoring", tags=["Эксплуатация"])


class MonitoringConfiguration(BaseSchema):
    enabled: bool = False
    public_key: str | None = None
    project_id: str | None = None
    port: int = 8080
    environment: str = "production"


@monitoring_router.get("/config", response_model=StdResponse[MonitoringConfiguration])
async def configuration() -> StdResponse[MonitoringConfiguration]:
    key = os.environ.get("FLUTTER_SENTRY_PUBLIC_KEY", "")
    project = os.environ.get("FLUTTER_SENTRY_PROJECT_ID", "")
    try:
        port = int(os.environ.get("GLITCHTIP_PORT", "8080"))
    except ValueError:
        port = 0
    enabled = (
        os.environ.get("FLUTTER_MONITORING_ENABLED", "false").lower() == "true"
        and re.fullmatch(r"[a-fA-F0-9]{32}", key) is not None
        and re.fullmatch(r"[1-9][0-9]*", project) is not None
        and 1 <= port <= 65535
    )
    return StdResponse(data=MonitoringConfiguration(
        enabled=enabled, public_key=key if enabled else None,
        project_id=project if enabled else None, port=port if enabled else 8080,
        environment=os.environ.get("SENTRY_ENVIRONMENT", "production"),
    ))
