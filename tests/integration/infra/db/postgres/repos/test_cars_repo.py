import pytest
from src.core.uuid7 import uuid7

from src.domain.cars.entities import Car
from src.infra.db.postgres.repos.cars.cars_repo import CarsRepository


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

        result = await repository.get_all()

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

        await repository.update(car)

        assert car.get_changes() == {}

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
        assert "is_active" in car.get_changes()

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

        from src.domain.cars.car_excs import CarNumberAlreadyExistsException
        with pytest.raises(CarNumberAlreadyExistsException) as exc_info:
            await repository.update(car1)

        assert exc_info.value.number == car2.number
