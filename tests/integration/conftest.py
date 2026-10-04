from collections.abc import AsyncGenerator, Callable, Coroutine
from dataclasses import dataclass
from os import environ
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from uuid6 import uuid7

from src.domain.employees.entities import Employee
from src.infra.db.postgres.database import Postgres
from src.infra.db.postgres.uow.employees import EmployeesUOW
from src.infra.services.password.service import PasswordService


@dataclass(frozen=True, slots=True)
class EmployeeTestData:
    """Данные сотрудника, подготовленного для интеграционного теста."""

    employee: Employee
    password: str

    @property
    def employee_id(self) -> UUID:
        return self.employee.employee_id

    @property
    def username(self) -> str:
        return self.employee.username


@pytest.fixture
def config_dir() -> Path:
    return Path(environ["CONFIG_DIR"])


@pytest.fixture
async def postgres() -> AsyncGenerator[Postgres, Any]:
    postgres = Postgres()
    yield postgres
    await postgres.dispose()


@pytest.fixture
def employees_uow_factory(
    postgres: Postgres,
) -> Callable[[], EmployeesUOW]:
    """Возвращает фабрику UOW с новой AsyncSession на каждый UOW."""

    def factory() -> EmployeesUOW:
        return EmployeesUOW(
            session_factory=postgres.session_factory,
        )

    return factory


@pytest.fixture
def password_service() -> PasswordService:
    """Реальный сервис паролей приложения для подготовки тестовых данных."""

    return PasswordService()


@pytest.fixture
def employee_factory(
    employees_uow_factory: Callable[[], EmployeesUOW],
    password_service: PasswordService,
) -> Callable[..., Coroutine[Any, Any, EmployeeTestData]]:
    """Создаёт сотрудника через EmployeesUOW и фиксирует его в PostgreSQL."""

    async def factory(
        *,
        username: str | None = None,
        password: str = "test_password",
        role: str = "employee",
        is_active: bool = True,
    ) -> EmployeeTestData:
        username = username or f"test_{uuid7()}"

        employee = Employee.create(
            actor_id=uuid7(),
            username=username,
            password_hash=password_service.hash(password=password),
            role=role,
        )

        if not is_active:
            employee.deactivate(actor_id=uuid7())

        async with employees_uow_factory() as uow:
            await uow.employees.add(employee)
            await uow.commit(events=employee.pull_events())

        return EmployeeTestData(
            employee=employee,
            password=password,
        )

    return factory


@pytest.fixture
async def active_employee(
    employee_factory: Callable[..., Coroutine[Any, Any, EmployeeTestData]],
) -> EmployeeTestData:
    return await employee_factory()


@pytest.fixture
async def inactive_employee(
    employee_factory: Callable[..., Coroutine[Any, Any, EmployeeTestData]],
) -> EmployeeTestData:
    return await employee_factory(is_active=False)
