from typing import Any, Self
from uuid import UUID

from sqlalchemy import Float, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.uuid7 import uuid7
from src.domain.cars import events
from src.domain.cars.car_excs import CarDomainUpdateException
from src.domain.common.entities import BaseEntity


class Car(BaseEntity):
    __tablename__ = "cars"

    car_id: Mapped[UUID] = mapped_column(primary_key=True)
    model: Mapped[str] = mapped_column(Text, index=True)

    UQ_NUMBER = "cars_number_key"
    number: Mapped[str] = mapped_column(
        Text,
        UniqueConstraint(name=UQ_NUMBER),
        index=True,
    )

    current_mileage: Mapped[float] = mapped_column(Float, default=0)
    is_active: Mapped[bool] = mapped_column(default=True)


    _ALLOWED_UPDATE_FIELDS = {
        "model",
        "number",
        "current_mileage",
        "is_active",
    }

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
            car_id=uuid7(),
            model=model,
            number=number,
            current_mileage=current_mileage,
            is_active=True,
        )

        car._add_event(
            events.CreateCarEvent(
                actor_id=actor_id,
                car_id=car.car_id,
            ),
        )

        return car

    def update(
        self,
        *,
        actor_id: UUID,
        **payload: Any,
    ) -> None:
        self._validate_update(payload)

        changes = self._apply_update_changes(
            payload=payload,
            allowed_fields=self._ALLOWED_UPDATE_FIELDS,
        )

        if not changes:
            return

        self._add_event(
            events.UpdateCarEvent(
                actor_id=actor_id,
                car_id=self.car_id,
                changes=changes,
            ),
        )

    def _validate_update(self, payload: dict[str, Any]) -> None:
        new_mileage = payload.get("current_mileage")

        if new_mileage is not None and new_mileage < self.current_mileage:
            raise CarDomainUpdateException(
                field="current_mileage",
                message=(
                    f"New mileage ({new_mileage}) cannot be less "
                    f"than current mileage ({self.current_mileage})."
                ),
            )
