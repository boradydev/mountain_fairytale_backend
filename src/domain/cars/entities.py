from dataclasses import dataclass
from typing import Any, Self
from uuid import UUID

from uuid6 import uuid7

from src.domain.common.entities import BaseEntity
from src.domain.cars import events


@dataclass(slots=True, kw_only=True)
class Car(BaseEntity):
    _car_id: UUID
    _model: str
    _number: str
    _current_mileage: float

    ID_FIELD = "car_id"

    _ALLOWED_UPDATE_FIELDS = {
        "model",
        "number",
        "current_mileage",
    }

    UPDATABLE_DATABASE_COLUMNS = frozenset([
        "model",
        "number",
        "current_mileage",
    ])

    @classmethod
    def create(
        cls,
        *,
        actor_id: UUID,
        model: str,
        number: str,
        current_mileage: float = 0,
    ) -> Self:
        car = cls(
            _car_id=uuid7(),
            _model=model,
            _number=number,
            _current_mileage=current_mileage,
        )

        car._add_event(
            events.CreateCarEvent(
                actor_id=actor_id,
                car_id=car._car_id,
            ),
        )

        return car

    def update(
        self,
        *,
        actor_id: UUID,
        **payload: Any,
    ) -> None:
        changes = self._apply_update_changes(
            payload=payload,
            allowed_fields=self._ALLOWED_UPDATE_FIELDS,
        )

        if not changes:
            return

        self._add_event(
            events.UpdateCarEvent(
                actor_id=actor_id,
                car_id=self._car_id,
                changes=changes,
            ),
        )

    def delete(
        self,
        *,
        actor_id: UUID,
    ) -> None:
        self._add_event(
            events.DeleteCarEvent(
                actor_id=actor_id,
                car_id=self._car_id,
            ),
        )

    @property
    def car_id(self) -> UUID:
        return self._car_id

    @property
    def model(self) -> str:
        return self._model

    @property
    def number(self) -> str:
        return self._number

    @property
    def current_mileage(self) -> float:
        return self._current_mileage