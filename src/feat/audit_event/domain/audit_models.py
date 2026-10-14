from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AuditEventView:
    event_id: UUID
    operation_id: UUID
    event_type: str
    created_at: datetime
    actor: dict[str, Any]
    action: str
    subject: dict[str, Any]
    data: dict[str, Any]
    changes: dict[str, Any]


@dataclass(frozen=True, slots=True)
class AuditPage:
    events: list[AuditEventView]
    next_cursor: str | None
    latest_cursor: str | None = None
