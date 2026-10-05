from datetime import datetime
from typing import Any, Self
from uuid import UUID

from sqlalchemy import DateTime, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.uuid7 import uuid7
from src.domain.common.entities import BaseEntity
from src.domain.employees import events


class Employee(BaseEntity):
    __tablename__ = "employees"

    employee_id: Mapped[UUID] = mapped_column(primary_key=True)

    UQ_USERNAME = "employees_username_key"
    username: Mapped[str] = mapped_column(
        Text,
        UniqueConstraint(name=UQ_USERNAME),
        index=True,
    )

    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)


    _ALLOWED_UPDATE_FIELDS = {
        "username",
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

    def change_password(
        self,
        actor_id: UUID,
        new_password_hash: str,
    ) -> None:
        self.password_hash = new_password_hash

        self._add_event(
            events.UpdateEmployeeEvent(
                actor_id=actor_id,
                employee_id=self.employee_id,
                changes={"password_hash": new_password_hash},
            ),
        )
