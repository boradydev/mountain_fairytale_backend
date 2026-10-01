from dataclasses import dataclass
from datetime import datetime
from typing import Any, Self
from uuid import UUID

from uuid6 import uuid7

from src.domain.common.entities import BaseEntity
from src.domain.employees import events


@dataclass(slots=True, kw_only=True)
class Employee(BaseEntity):
    _employee_id: UUID
    _username: str
    _password_hash: str
    _role: str
    _is_active: bool
    _created_at: datetime

    # Единственный источник правды для ID и колонок
    ID_FIELD = "employee_id"

    # Поля, доступные для изменения через общий метод update()
    _ALLOWED_UPDATE_FIELDS = {
        "username",
        "password_hash",
    }

    # ЕДИНСТВЕННАЯ ТОЧКА ПРАВДЫ ДЛЯ БАЗЫ ДАННЫХ
    # Сюда входят вообще все поля домена, которые могут измениться в течение жизни сущности
    UPDATABLE_DATABASE_COLUMNS = frozenset([
        "username",
        "password_hash",
        "is_active"
    ])

    @classmethod
    def create(
        cls,
        actor_id: UUID,
        username: str,
        password_hash: str,
    ) -> Self:
        employee = cls(
            _employee_id=uuid7(),
            _username=username,
            _password_hash=password_hash,
            _role="employee",
            _is_active=True,
            _created_at=datetime.now(),
        )

        employee._add_event(
            events.CreateEmployeeEvent(
                actor_id=actor_id,
                employee_id=employee._employee_id,
                created_at=employee._created_at,
            )
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
                employee_id=self._employee_id,
                changes=changes,
            )
        )

    def deactivate(self, actor_id: UUID) -> None:
        if not self._is_active:
            return

        change = self._apply_update_changes(
            payload={"is_active": False},
            allowed_fields={"is_active"},
        )

        self._add_event(
            events.UpdateEmployeeEvent(
                actor_id=actor_id,
                employee_id=self._employee_id,
                changes=change,
            )
        )

    def activate(self, actor_id: UUID) -> None:
        if self._is_active:
            return

        change = self._apply_update_changes(
            payload={"is_active": True},
            allowed_fields={"is_active"},
        )

        self._add_event(
            events.UpdateEmployeeEvent(
                actor_id=actor_id,
                employee_id=self._employee_id,
                changes=change,
            )
        )

    @property
    def employee_id(self) -> UUID:
        return self._employee_id

    @property
    def username(self) -> str:
        return self._username

    @property
    def password_hash(self) -> str:
        return self._password_hash

    @property
    def role(self) -> str:
        return self._role

    @property
    def is_active(self) -> bool:
        return self._is_active

    @property
    def created_at(self) -> datetime:
        return self._created_at
