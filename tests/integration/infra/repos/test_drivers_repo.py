import pytest

from src.core.uuid7 import uuid7
from src.feat.drivers.domain.driver_entities import Driver
from src.feat.drivers.infra.driver_repos import DriversRepository


@pytest.mark.integration
async def test_add_and_get_by_id(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = DriversRepository(session=session)

        driver = Driver.create(
            actor_id=uuid7(),
            name="Иван Иванов",
        )

        await repository.add(driver)
        await session.commit()

        result = await repository.get_by_id(driver.driver_id)

        assert result is not None
        assert result.driver_id == driver.driver_id
        assert result.name == driver.name
        assert result.is_active is True


@pytest.mark.integration
async def test_get_by_id_returns_none_for_unknown_driver(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = DriversRepository(session=session)

        result = await repository.get_by_id(uuid7())

        assert result is None


@pytest.mark.integration
async def test_get_all_excludes_deactivated_by_default(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = DriversRepository(session=session)

        active_driver = Driver.create(
            actor_id=uuid7(),
            name="Active",
        )
        inactive_driver = Driver.create(
            actor_id=uuid7(),
            name="Inactive",
        )
        inactive_driver.update(
            actor_id=uuid7(),
            is_active=False,
        )

        await repository.add(active_driver)
        await repository.add(inactive_driver)
        await session.commit()

        result = await repository.get_all(include_deactivated=False)

        assert {driver.driver_id for driver in result} == {
            active_driver.driver_id,
        }


@pytest.mark.integration
async def test_get_all_includes_deactivated_when_requested(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = DriversRepository(session=session)

        active_driver = Driver.create(
            actor_id=uuid7(),
            name="Active",
        )
        inactive_driver = Driver.create(
            actor_id=uuid7(),
            name="Inactive",
        )
        inactive_driver.update(
            actor_id=uuid7(),
            is_active=False,
        )

        await repository.add(active_driver)
        await repository.add(inactive_driver)
        await session.commit()

        result = await repository.get_all(include_deactivated=True)

        assert {driver.driver_id for driver in result} == {
            active_driver.driver_id,
            inactive_driver.driver_id,
        }


@pytest.mark.integration
async def test_update_persists_changes(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = DriversRepository(session=session)

        driver = Driver.create(
            actor_id=uuid7(),
            name="Old Name",
        )

        await repository.add(driver)
        await session.commit()

        driver.update(
            actor_id=uuid7(),
            name="New Name",
        )

        await repository.update(driver)
        await session.commit()

        result = await repository.get_by_id(driver.driver_id)

        assert result is not None
        assert result.name == "New Name"


@pytest.mark.integration
async def test_search_by_fuzzy_returns_best_match(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = DriversRepository(session=session)

        exact = Driver.create(
            actor_id=uuid7(),
            name="Александр",
        )
        similar = Driver.create(
            actor_id=uuid7(),
            name="Александр Сергеевич",
        )
        unrelated = Driver.create(
            actor_id=uuid7(),
            name="Петр",
        )

        await repository.add(exact)
        await repository.add(similar)
        await repository.add(unrelated)
        await session.commit()

        result = await repository.search_by_fuzzy(name="Александр")

        assert result is not None
        assert result.driver_id == exact.driver_id


@pytest.mark.integration
async def test_search_by_fuzzy_returns_none_without_match(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = DriversRepository(session=session)

        driver = Driver.create(
            actor_id=uuid7(),
            name="Иван Иванов",
        )

        await repository.add(driver)
        await session.commit()

        result = await repository.search_by_fuzzy(
            name="Совершенно Другое Имя",
        )

        assert result is None
