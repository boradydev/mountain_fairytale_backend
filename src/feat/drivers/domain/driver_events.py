from dataclasses import dataclass
from typing import Any
from uuid import UUID

from src.domain.common.events import BaseDomainEvent


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateDriverEvent(BaseDomainEvent):
    actor_id: UUID
    driver_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class UpdateDriverEvent(BaseDomainEvent):
    actor_id: UUID
    driver_id: UUID
    changes: dict[str, Any]
