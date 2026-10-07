from dataclasses import dataclass
from typing import Any
from uuid import UUID

from src.common.domain.events import BaseDomainEvent


@dataclass(frozen=True, slots=True, kw_only=True)
class CreatePaymentMethodEvent(BaseDomainEvent):
    actor_id: UUID
    payment_method_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class UpdatePaymentMethodEvent(BaseDomainEvent):
    actor_id: UUID
    payment_method_id: UUID
    changes: dict[str, Any]
