import pytest

from src.core.uuid7 import uuid7
from src.feat.employees.domain.employee_entities import Employee
from src.feat.employees.domain.employee_excs import EmployeeUsernameAlreadyExistsException
from src.feat.employees.infra.employee_repos import EmployeesRepository
from tests.helpers import unique_username
from collections.abc import AsyncGenerator
from typing import Any


PASSWORD_HASH = "test-password-hash"


@pytest.fixture(autouse=True)
async def clean_employees_table(postgres) -> AsyncGenerator[None, Any]:
    """Автоматически очищает таблицу сотрудников перед каждым тестом в модуле."""
    await postgres.execute("TRUNCATE TABLE employees RESTART IDENTITY CASCADE;")

    yield
    pass


@pytest.mark.integration
async def test_add_and_get_by_id(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = EmployeesRepository(session=session)

        employee = Employee.create(
            actor_id=uuid7(),
            username=unique_username(),
            password_hash=PASSWORD_HASH,
            role="employee",
        )

        await repository.add(employee)
        await session.commit()

        result = await repository.get_by_id(employee.employee_id)

        assert result is not None
        assert result.employee_id == employee.employee_id
        assert result.username == employee.username
        assert result.password_hash == PASSWORD_HASH
        assert result.role == "employee"
        assert result.is_active is True


@pytest.mark.integration
async def test_get_by_id_returns_none_for_unknown_employee(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = EmployeesRepository(session=session)

        result = await repository.get_by_id(uuid7())

        assert result is None


@pytest.mark.integration
async def test_get_by_username(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = EmployeesRepository(session=session)

        username = unique_username()
        employee = Employee.create(
            actor_id=uuid7(),
            username=username,
            password_hash=PASSWORD_HASH,
            role="employee",
        )

        await repository.add(employee)
        await session.commit()

        result = await repository.get_by_username(username)

        assert result is not None
        assert result.employee_id == employee.employee_id
        assert result.username == username


@pytest.mark.integration
async def test_get_by_username_returns_none_for_unknown_username(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = EmployeesRepository(session=session)

        result = await repository.get_by_username(unique_username("unknown"))

        assert result is None


@pytest.mark.integration
async def test_get_all_excludes_deactivated_by_default(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = EmployeesRepository(session=session)

        active = Employee.create(
            actor_id=uuid7(),
            username=unique_username("active"),
            password_hash=PASSWORD_HASH,
            role="employee",
        )
        inactive = Employee.create(
            actor_id=uuid7(),
            username=unique_username("inactive"),
            password_hash=PASSWORD_HASH,
            role="employee",
        )
        inactive.update(
            actor_id=uuid7(),
            is_active=False,
        )

        await repository.add(active)
        await repository.add(inactive)
        await session.commit()

        result = await repository.get_all(include_deactivated=False)

        assert {employee.employee_id for employee in result} == {
            active.employee_id,
        }


@pytest.mark.integration
async def test_get_all_includes_deactivated_when_requested(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = EmployeesRepository(session=session)

        active = Employee.create(
            actor_id=uuid7(),
            username=unique_username("active"),
            password_hash=PASSWORD_HASH,
            role="employee",
        )
        inactive = Employee.create(
            actor_id=uuid7(),
            username=unique_username("inactive"),
            password_hash=PASSWORD_HASH,
            role="employee",
        )
        inactive.update(
            actor_id=uuid7(),
            is_active=False,
        )

        await repository.add(active)
        await repository.add(inactive)
        await session.commit()

        result = await repository.get_all(include_deactivated=True)

        assert {employee.employee_id for employee in result} == {
            active.employee_id,
            inactive.employee_id,
        }


@pytest.mark.integration
async def test_update_persists_changes(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = EmployeesRepository(session=session)

        employee = Employee.create(
            actor_id=uuid7(),
            username=unique_username(),
            password_hash=PASSWORD_HASH,
            role="employee",
        )

        await repository.add(employee)
        await session.commit()

        new_username = unique_username("updated")

        employee.update(
            actor_id=uuid7(),
            username=new_username,
        )

        await repository.update(employee)
        await session.commit()

        result = await repository.get_by_id(employee.employee_id)

        assert result is not None
        assert result.username == new_username
        assert result.role == "employee"


@pytest.mark.integration
async def test_add_duplicate_username_raises_exception(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = EmployeesRepository(session=session)

        username = unique_username()

        first = Employee.create(
            actor_id=uuid7(),
            username=username,
            password_hash=PASSWORD_HASH,
            role="employee",
        )
        second = Employee.create(
            actor_id=uuid7(),
            username=username,
            password_hash=PASSWORD_HASH,
            role="employee",
        )

        await repository.add(first)
        await session.commit()

        with pytest.raises(EmployeeUsernameAlreadyExistsException) as exc_info:
            await repository.add(second)

        assert exc_info.value.username == username


@pytest.mark.integration
async def test_update_duplicate_username_raises_exception(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = EmployeesRepository(session=session)

        first = Employee.create(
            actor_id=uuid7(),
            username=unique_username("first"),
            password_hash=PASSWORD_HASH,
            role="employee",
        )
        second = Employee.create(
            actor_id=uuid7(),
            username=unique_username("second"),
            password_hash=PASSWORD_HASH,
            role="employee",
        )

        await repository.add(first)
        await repository.add(second)
        await session.commit()

        first.update(
            actor_id=uuid7(),
            username=second.username,
        )

        with pytest.raises(EmployeeUsernameAlreadyExistsException) as exc_info:
            await repository.update(first)

        assert exc_info.value.username == second.username
