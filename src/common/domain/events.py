from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class BaseDomainEvent:
    """Базовый класс для всех событий домена."""

    actor_id: UUID
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    subject_type: str | None = None
    subject_id: UUID | None = None
    name_fields: tuple[str, ...] = ()
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True, kw_only=True)
class FieldChange:
    old: Any
    new: Any
