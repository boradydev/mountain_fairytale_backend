from dataclasses import dataclass
from typing import Any
from uuid import UUID

from src.common.domain.events import BaseDomainEvent


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateProductEvent(BaseDomainEvent):
    actor_id: UUID
    product_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class UpdateProductEvent(BaseDomainEvent):
    actor_id: UUID
    product_id: UUID
    changes: dict[str, Any]
