from datetime import datetime
from typing import Any, Self
from uuid import UUID

from sqlalchemy import DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.core.uuid7 import uuid7
from src.domain.common.entities import BaseEntity
from src.domain.employees import events


class Employee(BaseEntity):
    __tablename__ = "employees"

    employee_id: Mapped[UUID] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(Text, unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)

    ID_FIELD = "employee_id"

    _ALLOWED_UPDATE_FIELDS = {
        "username",
        "password_hash",
        "is_active",
    }

    @classmethod
    def create(
        cls,
        actor_id: UUID,
        username: str,
        password_hash: str,
        role: str,
    ) -> Self:
        employee = cls(
            employee_id=uuid7(),
            username=username,
            password_hash=password_hash,
            role=role,
            is_active=True,
            created_at=datetime.now(),
        )

        employee._add_event(
            events.CreateEmployeeEvent(
                actor_id=actor_id,
                employee_id=employee.employee_id,
                created_at=employee.created_at,
            ),
        )

        return employee

    def update(
        self,
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
            events.UpdateEmployeeEvent(
                actor_id=actor_id,
                employee_id=self.employee_id,
                changes=changes,
            ),
        )
