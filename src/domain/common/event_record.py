from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class EventRecord:
    event_id: UUID
    event_type: str
    actor_id: UUID
    created_at: datetime
    payload: dict[str, Any]
