from datetime import datetime
from typing import Any, Self
from uuid import UUID

from sqlalchemy import DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.core.uuid7 import uuid7
from src.feat.drivers.domain import driver_events
from src.domain.common.entities import BaseEntity


class Driver(BaseEntity):
    __tablename__ = "app"

    driver_id: Mapped[UUID] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)

    _ALLOWED_UPDATE_FIELDS = {
        "name",
        "is_active",
    }

    @classmethod
    def create(
        cls,
        *,
        actor_id: UUID,
        name: str,
    ) -> Self:
        driver = cls(
            driver_id=uuid7(),
            name=name,
            is_active=True,
            created_at=datetime.now(),
        )

        driver._add_event(
            events.CreateDriverEvent(
                actor_id=actor_id,
                driver_id=driver.driver_id,
            ),
        )

        return driver

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
            events.UpdateDriverEvent(
                actor_id=actor_id,
                driver_id=self.driver_id,
                changes=changes,
            ),
        )
