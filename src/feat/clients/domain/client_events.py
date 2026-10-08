from dataclasses import dataclass
from typing import Any
from uuid import UUID

from src.common.domain.events import BaseDomainEvent


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateClientEvent(BaseDomainEvent):
    actor_id: UUID
    client_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class UpdateClientEvent(BaseDomainEvent):
    actor_id: UUID
    client_id: UUID
    changes: dict[str, Any]
