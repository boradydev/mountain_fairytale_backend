import pytest
from sqlalchemy import event
from src.core.uuid7 import uuid7
from src.feat.drivers.domain.driver_entities import Driver
from src.feat.drivers.infra.driver_repos import DriversRepository

@pytest.mark.integration
async def test_add_and_get_by_id(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = DriversRepository(session=session)
        driver = Driver.create(actor_id=uuid7(), name="Иван Иванов")
        
        await repository.add(driver)
        await session.commit()
        
        result = await repository.get_by_id(driver.driver_id)
        assert result is not None
        assert result.name == "Иван Иванов"
        assert result.is_active is True

@pytest.mark.integration
async def test_get_all_filter_active(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = DriversRepository(session=session)
        d1 = Driver.create(actor_id=uuid7(), name="Active 1")
        d2 = Driver.create(actor_id=uuid7(), name="Inactive 1")
        d2.update(actor_id=uuid7(), is_active=False)
        
        await repository.add(d1)
        await repository.add(d2)
        await session.commit()
        
        # Только активные
        active_list = await repository.get_all(include_deactivated=False)
        assert len(active_list) == 1
        assert active_list[0].driver_id == d1.driver_id
        
        # Все
        all_list = await repository.get_all(include_deactivated=True)
        assert len(all_list) == 2

@pytest.mark.integration
async def test_update_without_changes_does_nothing(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = DriversRepository(session=session)
        driver = Driver.create(actor_id=uuid7(), name="No Change")
        await repository.add(driver)
        await session.commit()
        
        sql_statements = []
        def before_cursor_execute(statement):
            sql_statements.append(statement)
            
        conn = await session.connection()
        event.listen(conn.sync_connection, "before_cursor_execute", before_cursor_execute)
        
        try:
            await repository.update(driver)
            assert not any("UPDATE" in stmt for stmt in sql_statements)
        finally:
            event.remove(conn.sync_connection, "before_cursor_execute", before_cursor_execute)

@pytest.mark.integration
async def test_search_by_fuzzy_ranking(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = DriversRepository(session=session)
        # Создаем водителей для проверки ранжирования: similarity -> length_delta -> created_at
        d1 = Driver.create(actor_id=uuid7(), name="Александр Сергеевич") # Точное
        d2 = Driver.create(actor_id=uuid7(), name="Александр")           # Похожее, короче
        d3 = Driver.create(actor_id=uuid7(), name="Алекс")                # Похожее, очень короткое
        
        await repository.add(d1)
        await repository.add(d2)
        await repository.add(d3)
        await session.commit()
        
        result = await repository.search_by_fuzzy(name="Александр")
        assert result is not None
        assert result.driver_id == d2.driver_id # Самый близкий по длине и similarity
