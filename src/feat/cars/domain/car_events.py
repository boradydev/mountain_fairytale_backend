from dataclasses import dataclass
from typing import Any
from uuid import UUID

from src.domain.common.events import BaseDomainEvent


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateCarEvent(BaseDomainEvent):
    actor_id: UUID
    car_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class UpdateCarEvent(BaseDomainEvent):
    actor_id: UUID
    car_id: UUID
    changes: dict[str, Any]
