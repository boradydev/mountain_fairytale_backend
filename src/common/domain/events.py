from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class BaseDomainEvent:
    """Базовый класс для всех событий домена."""

    created_at: datetime = field(
        default_factory=datetime.now,
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class FieldChange:
    old: Any
    new: Any
