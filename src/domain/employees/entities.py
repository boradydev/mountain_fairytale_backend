from dataclasses import dataclass
from datetime import datetime
from typing import Any, Self

from uuid6 import UUID, uuid7

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

    _ALLOWED_UPDATE_FIELDS = {"username", "password_hash"}

    def deactivate(self):
        self._is_active = False

    def activate(self):
        self._is_active = True

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
    def is_active(self) -> bool:
        return self._is_active

    @property
    def created_at(self) -> datetime:
        return self._created_at

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
        # 2. Вычисляем дельту изменений и мутируем состояние
        changes = self._apply_update_changes(
            payload=payload,
            allowed_fields=self._ALLOWED_UPDATE_FIELDS,
        )

        # 3. Если изменения были, регистрируем событие
        if changes:
            self._add_event(
                events.UpdateEmployeeEvent(
                    actor_id=actor_id,
                    employee_id=self._employee_id,
                    changes=changes,
                )
            )
