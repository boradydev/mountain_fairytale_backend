import pytest
from src.core.uuid7 import uuid7

from src.feat.employees.domain.employee_entities import Employee
from src.feat.employees.infra.employee_repos import EmployeesRepository
from tests.helpers import unique_username


@pytest.mark.integration
async def test_add_and_get_by_id(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = EmployeesRepository(session=session)
        username = unique_username("alex")

        employee = Employee.create(
            actor_id=uuid7(),
            username=username,
            password_hash="hash",
            role="employee"
        )

        await repository.add(employee)
        await session.commit()

        result = await repository.get_by_id(
            employee.employee_id,
        )

        assert result is not None
        assert result.employee_id == employee.employee_id
        assert result.username == username
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
        username1 = unique_username("alex")
        username2 = unique_username("petr")

        first = Employee.create(
            actor_id=uuid7(),
            username=username1,
            password_hash="hash1",
            role="employee"
        )

        second = Employee.create(
            actor_id=uuid7(),
            username=username2,
            password_hash="hash2",
            role="employee"
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
        username_original = unique_username("alex")
        username_new = unique_username("alexander")

        employee = Employee.create(
            actor_id=uuid7(),
            username=username_original,
            password_hash="original_hash",
            role="employee"
        )

        await repository.add(employee)
        await session.commit()

        employee.update(
            actor_id=uuid7(),
            username=username_new,
        )

        await repository.update(employee)

        assert employee.get_changes() == {}

        await session.commit()

        result = await repository.get_by_id(
            employee.employee_id,
        )

        assert result is not None
        assert result.username == username_new
        assert result.password_hash == "original_hash"
        assert result.role == "employee"
        assert result.is_active is True


@pytest.mark.integration
async def test_update_multiple_fields_in_one_query(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = EmployeesRepository(session=session)
        username_original = unique_username("alex")
        username_new = unique_username("alexander")

        employee = Employee.create(
            actor_id=uuid7(),
            username=username_original,
            password_hash="original_hash",
            role="employee"
        )

        await repository.add(employee)
        await session.commit()

        employee.update(
            actor_id=uuid7(),
            username=username_new,
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
        assert result.username == username_new
        assert result.password_hash == "new_hash"
        assert result.is_active is True


@pytest.mark.integration
async def test_deactivate(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = EmployeesRepository(session=session)
        username = unique_username("alex")

        employee = Employee.create(
            actor_id=uuid7(),
            username=username,
            password_hash="hash",
            role="employee"
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


@pytest.mark.integration
async def test_update_without_changes_does_nothing(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = EmployeesRepository(session=session)
        # 1. Защищаем тест от UniqueViolationError динамическим именем
        username = unique_username("alex")

        employee = Employee.create(
            actor_id=uuid7(),
            username=username,
            password_hash="hash",
            role="employee"
        )

        await repository.add(employee)
        await session.commit()

        # Гарантируем, что изменений нет
        assert employee.get_changes() == {}

        # 2. Перехватываем выполнение SQL-запросов, чтобы убедиться,
        # что Алхимия не сделала ни одного лишнего UPDATE в базу
        from sqlalchemy import event

        sql_statements = []

        def before_cursor_execute(statement):
            sql_statements.append(statement)

        # Вешаем слушатель на текущее соединение
        conn = await session.connection()
        event.listen(conn.sync_connection, "before_cursor_execute", before_cursor_execute)

        try:
            # Вызываем обновление без изменений
            await repository.update(employee)

            # Проверяем, что среди выполненных строк кода не было команды UPDATE
            assert not any("UPDATE" in stmt for stmt in sql_statements), (
                "Холостой UPDATE улетел в базу данных!"
            )
        finally:
            # Обязательно убираем слушатель за собой
            event.remove(conn.sync_connection, "before_cursor_execute", before_cursor_execute)

        # Финальная проверка, что данные в базе остались в порядке
        result = await repository.get_by_id(employee.employee_id)
        assert result is not None
        assert result.username == username


@pytest.mark.integration
async def test_get_by_username(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = EmployeesRepository(session=session)
        username = unique_username("alex")

        employee = Employee.create(
            actor_id=uuid7(),
            username=username,
            password_hash="hash",
            role="employee"
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

        result = await repository.get_by_username("non_existent_user")

        assert result is None
