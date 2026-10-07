from dataclasses import dataclass
from typing import Any
from uuid6 import UUID

from src.common.domain.events import BaseDomainEvent


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateEmployeeEvent(BaseDomainEvent):
    actor_id: UUID
    employee_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class UpdateEmployeeEvent(BaseDomainEvent):
    actor_id: UUID
    employee_id: UUID
    changes: dict[str, Any]


@dataclass(frozen=True, slots=True, kw_only=True)
class EmployeeLoginEvent(BaseDomainEvent):
    actor_id: UUID