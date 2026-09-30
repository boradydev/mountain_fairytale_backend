from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class BaseDomainEvent:
    """Базовый класс для всех событий домена."""

    created_at: datetime = datetime.now()


@dataclass(frozen=True, slots=True, kw_only=True)
class FieldChange:
    old: str
    new: str
