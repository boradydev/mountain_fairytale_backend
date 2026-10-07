from dataclasses import dataclass
from typing import Any
from uuid import UUID

from src.common.domain.events import BaseDomainEvent


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateSalesRepresentativeEvent(BaseDomainEvent):
    actor_id: UUID
    sales_representative_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class UpdateSalesRepresentativeEvent(BaseDomainEvent):
    actor_id: UUID
    sales_representative_id: UUID
    changes: dict[str, Any]
