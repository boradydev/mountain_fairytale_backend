import pytest
from uuid6 import uuid7

from src.domain.employees.entities import Employee
from src.infra.db.postgres.repos.employees.repo import EmployeesRepository


@pytest.mark.integration
async def test_add_and_get_by_id(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = EmployeesRepository(session=session)

        employee = Employee.create(
            actor_id=uuid7(),
            username="alex",
            password_hash="hash",
        )

        await repository.add(employee)
        await session.commit()

        result = await repository.get_by_id(
            employee.employee_id,
        )

        assert result is not None
        assert result.employee_id == employee.employee_id
        assert result.username == "alex"
        assert result.password_hash == "hash"
        assert result.role == "employee"
        assert result.is_active is True
        assert result.created_at == employee.created_at


@pytest.mark.integration
async def test_get_by_id_returns_none_for_unknown_employee(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = EmployeesRepository(session=session)

        result = await repository.get_by_id(uuid7())

        assert result is None


@pytest.mark.integration
async def test_get_all(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = EmployeesRepository(session=session)

        first = Employee.create(
            actor_id=uuid7(),
            username="alex",
            password_hash="hash1",
        )

        second = Employee.create(
            actor_id=uuid7(),
            username="petr",
            password_hash="hash2",
        )

        await repository.add(first)
        await repository.add(second)
        await session.commit()

        result = await repository.get_all()

        employee_ids = {employee.employee_id for employee in result}

        assert first.employee_id in employee_ids
        assert second.employee_id in employee_ids


@pytest.mark.integration
async def test_update_changes_only_modified_fields(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = EmployeesRepository(session=session)

        employee = Employee.create(
            actor_id=uuid7(),
            username="alex",
            password_hash="original_hash",
        )

        await repository.add(employee)
        await session.commit()

        employee.update(
            actor_id=uuid7(),
            username="alexander",
        )

        await repository.update(employee)

        assert employee.get_changes() == {}

        await session.commit()

        result = await repository.get_by_id(
            employee.employee_id,
        )

        assert result is not None
        assert result.username == "alexander"
        assert result.password_hash == "original_hash"
        assert result.role == "employee"
        assert result.is_active is True


@pytest.mark.integration
async def test_update_multiple_fields_in_one_query(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = EmployeesRepository(session=session)

        employee = Employee.create(
            actor_id=uuid7(),
            username="alex",
            password_hash="original_hash",
        )

        await repository.add(employee)
        await session.commit()

        employee.update(
            actor_id=uuid7(),
            username="alexander",
            password_hash="new_hash",
        )

        changes = employee.get_changes()

        assert set(changes) == {
            "username",
            "password_hash",
        }

        await repository.update(employee)
        await session.commit()

        result = await repository.get_by_id(
            employee.employee_id,
        )

        assert result is not None
        assert result.username == "alexander"
        assert result.password_hash == "new_hash"
        assert result.is_active is True


@pytest.mark.integration
async def test_deactivate(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = EmployeesRepository(session=session)

        employee = Employee.create(
            actor_id=uuid7(),
            username="alex",
            password_hash="hash",
        )

        await repository.add(employee)
        await session.commit()

        employee.deactivate(
            actor_id=uuid7(),
        )

        assert employee.is_active is False
        assert "is_active" in employee.get_changes()

        await repository.update(employee)
        await session.commit()

        result = await repository.get_by_id(
            employee.employee_id,
        )

        assert result is not None
        assert result.is_active is False
