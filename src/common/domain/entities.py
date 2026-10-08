from typing import Any

from sqlalchemy.orm import reconstructor

from src.common.domain.events import BaseDomainEvent, FieldChange
from src.common.domain.base_model import BaseModel


class BaseEntity(BaseModel):
    __abstract__ = True

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._events: list[BaseDomainEvent] = []

    @reconstructor
    def _init_on_load(self) -> None:
        self._events = []

    def _add_event(self, event: BaseDomainEvent) -> None:
        self._events.append(event)

    def pull_events(self) -> list[BaseDomainEvent]:
        events = self._events.copy()
        self._events.clear()
        return events

    def _apply_update_changes(
        self,
        payload: dict[str, Any],
        allowed_fields: set[str],
    ) -> dict[str, FieldChange]:
        changes: dict[str, FieldChange] = {}

        for key, new_value in payload.items():
            if key not in allowed_fields:
                continue

            current_value = getattr(self, key)

            if current_value == new_value:
                continue

            changes[key] = FieldChange(
                old=current_value,
                new=new_value,
            )

            setattr(self, key, new_value)

        return changes
