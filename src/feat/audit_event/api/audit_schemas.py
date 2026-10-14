from datetime import datetime
from uuid import UUID

from pydantic import Field, JsonValue

from src.common.api.schemas import BaseSchema


class AuditActorResp(BaseSchema):
    actor_id: UUID
    display_name: str | None


class AuditSubjectResp(BaseSchema):
    type: str
    id: UUID
    display_name: str | None


class AuditChangeResp(BaseSchema):
    old_value: JsonValue
    new_value: JsonValue


class AuditEventResp(BaseSchema):
    event_id: UUID
    operation_id: UUID
    event_type: str
    created_at: datetime
    actor: AuditActorResp
    action: str
    subject: AuditSubjectResp
    data: dict[str, JsonValue] = Field(default_factory=dict)
    changes: dict[str, AuditChangeResp]


class AuditPageResp(BaseSchema):
    events: list[AuditEventResp]
    next_cursor: str | None
