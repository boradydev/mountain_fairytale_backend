from dataclasses import replace
from typing import Any, ClassVar
from uuid import UUID

from sqlalchemy.orm import reconstructor

from src.common.domain.base_model import BaseModel
from src.common.domain.events import BaseDomainEvent, FieldChange


class BaseEntity(BaseModel):
    __abstract__ = True
    _EVENT_FIELDS: ClassVar[set[str]] = set()
    _EVENT_SUBJECT_TYPE: ClassVar[str] = ""
    _EVENT_ID_FIELD: ClassVar[str] = ""
    _EVENT_NAME_FIELDS: ClassVar[tuple[str, ...]] = ("name",)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._events: list[BaseDomainEvent] = []

    @reconstructor
    def _init_on_load(self) -> None:
        self._events = []

    def _add_event(self, event: BaseDomainEvent) -> None:
        changes = getattr(event, "changes", {})
        if not self._EVENT_FIELDS or set(changes) - self._EVENT_FIELDS:
            raise ValueError(f"Unsupported audit fields for {type(self).__name__}")
        data = {}
        if type(event).__name__.startswith(("Create", "Delete")):
            data = self._event_snapshot()
            if set(data) - (self._EVENT_FIELDS | {"display_name"}):
                raise ValueError(f"Unsupported audit snapshot for {type(self).__name__}")
        event = replace(
            event,
            subject_type=self._EVENT_SUBJECT_TYPE,
            subject_id=self._event_subject_id(),
            name_fields=self._EVENT_NAME_FIELDS,
            data=data,
        )
        self._events.append(event)

    def _event_subject_id(self) -> UUID:
        return getattr(self, self._EVENT_ID_FIELD)

    def _event_snapshot(self) -> dict[str, Any]:
        values = {key: getattr(self, key) for key in sorted(self._EVENT_FIELDS)}
        values["display_name"] = " ".join(str(values[key]) for key in self._EVENT_NAME_FIELDS if key in values)
        return values

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
