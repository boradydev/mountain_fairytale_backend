from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from src.core.uuid7 import uuid7


@dataclass(frozen=True, slots=True, kw_only=True)
class EventRecord:
    event_id: UUID
    event_type: str
    actor_id: UUID
    created_at: datetime
    payload: dict[str, Any]
    operation_id: UUID = field(default_factory=uuid7)


@dataclass(frozen=True, slots=True, kw_only=True)
class AuditRecord(EventRecord):
    actor_name: str | None
    subject_name: str | None
    action: str
    document_type: str | None = None
