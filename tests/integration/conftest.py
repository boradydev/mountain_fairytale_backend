from collections.abc import AsyncGenerator, Callable, Coroutine
from dataclasses import dataclass
from os import environ
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from src.common.infra.db.postgres.database import Postgres
from src.common.infra.services.password_service import PasswordService
from src.core.uuid7 import uuid7
from src.feat.cars.domain.car_entities import Car
from src.feat.cars.infra.car_uow import CarsUOW
from src.feat.clients.domain.client_entities import Client
from src.feat.clients.infra.client_uow import ClientsUOW
from src.feat.employees.domain.employee_entities import Employee
from src.feat.employees.infra.employee_uow import EmployeesUOW
from tests.helpers import unique_car_number, unique_username


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


@dataclass(frozen=True, slots=True)
class ClientTestData:
    """Данные клиента, подготовленного для интеграционного теста."""

    client: Client

    @property
    def client_id(self) -> UUID:
        return self.client.client_id

    @property
    def name(self) -> str:
        return self.client.name

    @property
    def phone(self) -> str:
        return self.client.phone

    @property
    def address(self) -> str:
        return self.client.address

    @property
    def is_active(self) -> bool:
        return self.client.is_active


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
    def factory() -> EmployeesUOW:
        return EmployeesUOW(session_factory=postgres.session_factory)

    return factory


@pytest.fixture
def cars_uow_factory(
    postgres: Postgres,
) -> Callable[[], CarsUOW]:
    def factory() -> CarsUOW:
        return CarsUOW(session_factory=postgres.session_factory)

    return factory


@pytest.fixture
def clients_uow_factory(
    postgres: Postgres,
) -> Callable[[], ClientsUOW]:
    def factory() -> ClientsUOW:
        return ClientsUOW(session_factory=postgres.session_factory)

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
    async def factory(
        *,
        username: str | None = None,
        password: str = "test_password",
        role: str = "employee",
        commission_percent: float = 0.0,
        is_active: bool = True,
    ) -> EmployeeTestData:
        employee = Employee.create(
            actor_id=uuid7(),
            username=username or unique_username(),
            password_hash=password_service.hash(password=password),
            role=role,
            commission_percent=commission_percent,
        )
        if not is_active:
            employee.update(actor_id=uuid7(), is_active=False)

        async with employees_uow_factory() as uow:
            await uow.employees.add(employee)
            await uow.commit(events=employee.pull_events())

        return EmployeeTestData(employee=employee, password=password)

    return factory


@pytest.fixture
def car_factory(
    cars_uow_factory: Callable[[], CarsUOW],
) -> Callable[..., Coroutine[Any, Any, CarTestData]]:
    async def factory(
        *,
        model: str = "Tesla Model 3",
        number: str | None = None,
        current_mileage: float = 0.0,
        is_active: bool = True,
    ) -> CarTestData:
        car = Car.create(
            actor_id=uuid7(),
            model=model,
            number=number or unique_car_number(),
            current_mileage=current_mileage,
        )
        if not is_active:
            car.update(actor_id=uuid7(), is_active=False)

        async with cars_uow_factory() as uow:
            await uow.cars.add(car)
            await uow.commit(events=car.pull_events())

        return CarTestData(car=car)

    return factory


@pytest.fixture
def client_factory(
    clients_uow_factory: Callable[[], ClientsUOW],
) -> Callable[..., Coroutine[Any, Any, ClientTestData]]:
    async def factory(
        *,
        name: str = "Тестовый клиент",
        phone: str | None = None,
        address: str = "Тестовый адрес",
        sleeping_threshold_days: int = 30,
        is_active: bool = True,
    ) -> ClientTestData:
        from uuid import uuid4

        client = Client.create(
            actor_id=uuid7(),
            name=name,
            phone=phone or uuid4().hex,
            address=address,
            sleeping_threshold_days=sleeping_threshold_days,
        )
        if not is_active:
            client.update(actor_id=uuid7(), is_active=False)

        async with clients_uow_factory() as uow:
            await uow.clients.add(client)
            await uow.commit(events=client.pull_events())

        return ClientTestData(client=client)

    return factory


@pytest.fixture
async def active_employee(
    employee_factory: Callable[..., Coroutine[Any, Any, EmployeeTestData]],
) -> EmployeeTestData:
    return await employee_factory()


@pytest.fixture
async def admin_employee(
    employee_factory: Callable[..., Coroutine[Any, Any, EmployeeTestData]],
) -> EmployeeTestData:
    return await employee_factory(role="admin")


@pytest.fixture
async def inactive_employee(
    employee_factory: Callable[..., Coroutine[Any, Any, EmployeeTestData]],
) -> EmployeeTestData:
    return await employee_factory(is_active=False)
