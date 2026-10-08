from datetime import datetime
from typing import Any, Self
from uuid import UUID

from sqlalchemy import DateTime, Float, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.uuid7 import uuid7
from src.common.domain.entities import BaseEntity
from src.feat.employees.domain.employee_events import UpdateEmployeeEvent, CreateEmployeeEvent


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
    commission_percent: Mapped[float] = mapped_column(Float)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)

    _ALLOWED_UPDATE_FIELDS = {
        "username",
        "commission_percent",
        "is_active",
    }

    @classmethod
    def create(
        cls,
        actor_id: UUID,
        username: str,
        password_hash: str,
        role: str,
        commission_percent: float,
    ) -> Self:
        employee = cls(
            employee_id=uuid7(),
            username=username,
            password_hash=password_hash,
            role=role,
            commission_percent=commission_percent,
            is_active=True,
            created_at=datetime.now(),
        )

        employee._add_event(
            CreateEmployeeEvent(
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
            UpdateEmployeeEvent(
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
            UpdateEmployeeEvent(
                actor_id=actor_id,
                employee_id=self.employee_id,
                changes={"password_hash": new_password_hash},
            ),
        )
