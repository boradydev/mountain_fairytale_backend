from dataclasses import dataclass, field
from typing import Any

from src.domain.common.events import BaseDomainEvent, FieldChange


@dataclass
class BaseEntity:
    _events: list[BaseDomainEvent] = field(
        init=False,
        repr=False,
        compare=False,
        default_factory=list,
    )

    _changes: dict[str, FieldChange] = field(
        init=False,
        repr=False,
        compare=False,
        default_factory=dict,
    )

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

            private_attr_name = f"_{key}"
            current_value = getattr(self, private_attr_name)

            if new_value is None or current_value == new_value:
                continue

            change = FieldChange(
                old=current_value,
                new=new_value,
            )

            changes[key] = change
            self._changes[key] = change

            setattr(self, private_attr_name, new_value)

        return changes

    def get_changes(self) -> dict[str, FieldChange]:
        return self._changes.copy()

    def clear_changes(self) -> None:
        self._changes.clear()
