from collections.abc import AsyncGenerator, Callable, Coroutine
from dataclasses import dataclass
from os import environ
from pathlib import Path
from typing import Any
from uuid import UUID

import random
import string
import pytest
from uuid6 import uuid7

from src.domain.employees.entities import Employee
from src.domain.cars.entities import Car
from src.infra.db.postgres.database import Postgres
from src.infra.db.postgres.uow.employees import EmployeesUOW
from src.infra.db.postgres.uow.cars import CarsUOW
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


@dataclass(frozen=True, slots=True)
class CarTestData:
    """Данные автомобиля, подготовленного для интеграционного теста."""

    car: Car

    @property
    def car_id(self) -> UUID:
        return self.car.car_id

    @property
    def model(self) -> str:
        return self.car.model

    @property
    def number(self) -> str:
        return self.car.number

    @property
    def is_active(self) -> bool:
        return self.car.is_active


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
def cars_uow_factory(
    postgres: Postgres,
) -> Callable[[], CarsUOW]:
    """Возвращает фабрику UOW с новой AsyncSession на каждый UOW."""

    def factory() -> CarsUOW:
        return CarsUOW(
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
def car_factory(
    cars_uow_factory: Callable[[], CarsUOW],
) -> Callable[..., Coroutine[Any, Any, CarTestData]]:
    """Создаёт автомобиль через CarsUOW и фиксирует его в PostgreSQL."""

    async def factory(
        *,
        model: str = "Tesla Model 3",
        number: str | None = None,
        current_mileage: float = 0.0,
        is_active: bool = True,
    ) -> CarTestData:
        number = number or f"A{''.join(random.choices(string.ascii_uppercase + string.digits, k=8))}XX"

        car = Car.create(
            actor_id=uuid7(),
            model=model,
            number=number,
            current_mileage=current_mileage,
        )

        if not is_active:
            car.deactivate(actor_id=uuid7())

        async with cars_uow_factory() as uow:
            await uow.cars.add(car)
            await uow.commit(events=car.pull_events())

        return CarTestData(
            car=car,
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
