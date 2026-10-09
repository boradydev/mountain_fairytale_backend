from dataclasses import dataclass
from typing import Any
from uuid import UUID

from src.common.domain.events import BaseDomainEvent


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateDeliveryDocumentEvent(BaseDomainEvent):
    actor_id: UUID
    delivery_document_id: UUID
    document_type: str


@dataclass(frozen=True, slots=True, kw_only=True)
class UpdateDeliveryDocumentEvent(BaseDomainEvent):
    actor_id: UUID
    delivery_document_id: UUID
    changes: dict[str, Any]


@dataclass(frozen=True, slots=True, kw_only=True)
class CancelDeliveryDocumentEvent(BaseDomainEvent):
    actor_id: UUID
    delivery_document_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class RestoreDeliveryDocumentEvent(BaseDomainEvent):
    actor_id: UUID
    delivery_document_id: UUID
