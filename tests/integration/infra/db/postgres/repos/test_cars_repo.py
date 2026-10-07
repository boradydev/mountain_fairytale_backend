import pytest
from sqlalchemy import event
from src.core.uuid7 import uuid7

from src.feat.cars.domain.car_entities import Car
from src.feat.cars.infra.car_repos import CarsRepository


@pytest.mark.integration
async def test_add_and_get_by_id(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = CarsRepository(session=session)
        
        number = f"CAR-{uuid7()}"
        car = Car.create(
            actor_id=uuid7(),
            model="Toyota Camry",
            number=number,
            current_mileage=1500.0
        )

        await repository.add(car)
        await session.commit()

        result = await repository.get_by_id(
            car.car_id,
        )

        assert result is not None
        assert result.car_id == car.car_id
        assert result.model == "Toyota Camry"
        assert result.number == number
        assert result.current_mileage == 1500.0
        assert result.is_active is True


@pytest.mark.integration
async def test_get_by_id_returns_none_for_unknown_car(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = CarsRepository(session=session)

        result = await repository.get_by_id(uuid7())

        assert result is None


@pytest.mark.integration
async def test_get_all(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = CarsRepository(session=session)
        
        car1 = Car.create(actor_id=uuid7(), model="Model 1", number=f"CAR-{uuid7()}")
        car2 = Car.create(actor_id=uuid7(), model="Model 2", number=f"CAR-{uuid7()}")

        await repository.add(car1)
        await repository.add(car2)
        await session.commit()

        result = await repository.get_all(include_deactivated=False)

        car_ids = {car.car_id for car in result}

        assert car1.car_id in car_ids
        assert car2.car_id in car_ids


@pytest.mark.integration
async def test_update_changes_only_modified_fields(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = CarsRepository(session=session)
        
        car = Car.create(
            actor_id=uuid7(),
            model="Old Model",
            number=f"CAR-{uuid7()}",
            current_mileage=100.0
        )

        await repository.add(car)
        await session.commit()

        car.update(
            actor_id=uuid7(),
            model="New Model",
        )

        # Проверяем, что событие обновления создано и содержит только измененное поле
        events = car.pull_events()
        assert len(events) == 1
        update_event = events[0]
        assert "model" in update_event.changes
        assert "number" not in update_event.changes

        await repository.update(car)

        await session.commit()

        result = await repository.get_by_id(
            car.car_id,
        )

        assert result is not None
        assert result.model == "New Model"
        assert result.number == car.number
        assert result.current_mileage == 100.0
        assert result.is_active is True


@pytest.mark.integration
async def test_deactivate(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = CarsRepository(session=session)
        
        car = Car.create(
            actor_id=uuid7(),
            model="Tesla",
            number=f"CAR-{uuid7()}",
        )

        await repository.add(car)
        await session.commit()

        car.deactivate(
            actor_id=uuid7(),
        )

        assert car.is_active is False
        
        # Проверяем наличие события деактивации
        events = car.pull_events()
        assert len(events) == 1
        assert "is_active" in events[0].changes

        await repository.update(car)
        await session.commit()

        result = await repository.get_by_id(
            car.car_id,
        )

        assert result is not None
        assert result.is_active is False


@pytest.mark.integration
async def test_get_by_number(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = CarsRepository(session=session)
        number = f"CAR-{uuid7()}"
        
        car = Car.create(
            actor_id=uuid7(),
            model="BMW",
            number=number,
        )

        await repository.add(car)
        await session.commit()

        result = await repository.get_by_number(number)

        assert result is not None
        assert result.car_id == car.car_id
        assert result.number == number


@pytest.mark.integration
async def test_get_by_number_returns_none_for_unknown_number(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = CarsRepository(session=session)

        result = await repository.get_by_number("NON_EXISTENT")

        assert result is None


@pytest.mark.integration
async def test_update_duplicate_number_raises_exception(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = CarsRepository(session=session)
        
        # Создаем два автомобиля с разными номерами
        car1 = Car.create(
            actor_id=uuid7(),
            model="Model 1",
            number=f"CAR-1-{uuid7()}",
        )
        car2 = Car.create(
            actor_id=uuid7(),
            model="Model 2",
            number=f"CAR-2-{uuid7()}",
        )

        await repository.add(car1)
        await repository.add(car2)
        await session.commit()

        # Пытаемся изменить номер первого автомобиля на номер второго
        car1.update(
            actor_id=uuid7(),
            number=car2.number,
        )

        from src.feat.cars.domain.car_excs import CarNumberAlreadyExistsException
        with pytest.raises(CarNumberAlreadyExistsException) as exc_info:
            await repository.update(car1)

        assert exc_info.value.number == car2.number


@pytest.mark.integration
async def test_update_without_changes_does_nothing(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = CarsRepository(session=session)
        car = Car.create(
            actor_id=uuid7(),
            model="No Change Model",
            number=f"CAR-{uuid7()}",
        )

        await repository.add(car)
        await session.commit()

        # Гарантируем, что событий нет (изменений не было)
        assert len(car.pull_events()) == 0

        sql_statements = []
        def before_cursor_execute(statement):
            sql_statements.append(statement)

        conn = await session.connection()
        event.listen(conn.sync_connection, "before_cursor_execute", before_cursor_execute)

        try:
            await repository.update(car)
            assert not any("UPDATE" in stmt for stmt in sql_statements), (
                "Холостой UPDATE улетел в базу данных!"
            )
        finally:
            event.remove(conn.sync_connection, "before_cursor_execute", before_cursor_execute)
