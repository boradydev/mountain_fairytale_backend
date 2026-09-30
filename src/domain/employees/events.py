from dataclasses import dataclass
from typing import Any

from uuid6 import UUID

from src.domain.common.events import BaseDomainEvent
from src.domain.employees import vals


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateEmployeeEvent(BaseDomainEvent):
    actor_id: UUID
    employee_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class UpdateEmployeeEvent(BaseDomainEvent):
    actor_id: UUID
    employee_id: UUID
    changes: dict[str, Any]