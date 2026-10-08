from collections.abc import AsyncGenerator
from typing import Any

import pytest

from src.core.uuid7 import uuid7
from src.feat.cars.domain.car_entities import Car
from src.feat.cars.domain.car_excs import CarNumberAlreadyExistsException
from src.feat.cars.infra.car_repos import CarsRepository
from tests.helpers import unique_car_number


@pytest.fixture(autouse=True)
async def clean_cars_table(postgres) -> AsyncGenerator[None, Any]:
    """Автоматически очищает таблицу машин перед каждым тестом в модуле."""
    await postgres.execute("TRUNCATE TABLE cars RESTART IDENTITY CASCADE;")

    yield
    pass


@pytest.mark.integration
async def test_add_and_get_by_id(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = CarsRepository(session=session)

        car = Car.create(
            actor_id=uuid7(),
            model="Toyota Camry",
            number=unique_car_number(),
            current_mileage=1500.0,
        )

        await repository.add(car)
        await session.commit()

        result = await repository.get_by_id(car.car_id)

        assert result is not None
        assert result.car_id == car.car_id
        assert result.model == car.model
        assert result.number == car.number
        assert result.current_mileage == 1500.0
        assert result.is_active is True


@pytest.mark.integration
async def test_get_by_id_returns_none_for_unknown_car(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = CarsRepository(session=session)

        result = await repository.get_by_id(uuid7())

        assert result is None


@pytest.mark.integration
async def test_get_by_number(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = CarsRepository(session=session)

        number = unique_car_number()
        car = Car.create(
            actor_id=uuid7(),
            model="Toyota Camry",
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

        result = await repository.get_by_number(unique_car_number())

        assert result is None


@pytest.mark.integration
async def test_get_all_excludes_deactivated_by_default(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = CarsRepository(session=session)

        active_car = Car.create(
            actor_id=uuid7(),
            model="Active",
            number=unique_car_number(),
        )
        inactive_car = Car.create(
            actor_id=uuid7(),
            model="Inactive",
            number=unique_car_number(),
        )
        inactive_car.update(
            actor_id=uuid7(),
            is_active=False,
        )

        await repository.add(active_car)
        await repository.add(inactive_car)
        await session.commit()

        result = await repository.get_all(include_deactivated=False)

        result_ids = {car.car_id for car in result}

        assert result_ids == {active_car.car_id}


@pytest.mark.integration
async def test_get_all_includes_deactivated_when_requested(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = CarsRepository(session=session)

        active_car = Car.create(
            actor_id=uuid7(),
            model="Active",
            number=unique_car_number(),
        )
        inactive_car = Car.create(
            actor_id=uuid7(),
            model="Inactive",
            number=unique_car_number(),
        )
        inactive_car.update(
            actor_id=uuid7(),
            is_active=False,
        )

        await repository.add(active_car)
        await repository.add(inactive_car)
        await session.commit()

        result = await repository.get_all(include_deactivated=True)

        result_ids = {car.car_id for car in result}

        assert result_ids == {
            active_car.car_id,
            inactive_car.car_id,
        }


@pytest.mark.integration
async def test_update_persists_changes(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = CarsRepository(session=session)

        car = Car.create(
            actor_id=uuid7(),
            model="Old Model",
            number=unique_car_number(),
            current_mileage=100.0,
        )

        await repository.add(car)
        await session.commit()

        car.update(
            actor_id=uuid7(),
            model="New Model",
            current_mileage=250.0,
        )

        await repository.update(car)
        await session.commit()

        result = await repository.get_by_id(car.car_id)

        assert result is not None
        assert result.model == "New Model"
        assert result.current_mileage == 250.0
        assert result.number == car.number


@pytest.mark.integration
async def test_add_duplicate_number_raises_exception(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = CarsRepository(session=session)

        number = unique_car_number()

        first = Car.create(
            actor_id=uuid7(),
            model="First",
            number=number,
        )
        second = Car.create(
            actor_id=uuid7(),
            model="Second",
            number=number,
        )

        await repository.add(first)
        await session.commit()

        with pytest.raises(CarNumberAlreadyExistsException) as exc_info:
            await repository.add(second)

        assert exc_info.value.number == number


@pytest.mark.integration
async def test_update_duplicate_number_raises_exception(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = CarsRepository(session=session)

        first = Car.create(
            actor_id=uuid7(),
            model="First",
            number=unique_car_number(),
        )
        second = Car.create(
            actor_id=uuid7(),
            model="Second",
            number=unique_car_number(),
        )

        await repository.add(first)
        await repository.add(second)
        await session.commit()

        second_number = second.number

        first.update(
            actor_id=uuid7(),
            number=second_number,
        )

        with pytest.raises(CarNumberAlreadyExistsException) as exc_info:
            await repository.update(first)

        assert exc_info.value.number == second_number
