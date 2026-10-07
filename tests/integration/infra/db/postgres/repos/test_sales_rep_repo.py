import pytest
from sqlalchemy import event
from src.core.uuid7 import uuid7
from src.feat.sales_rep.domain.sales_rep_entities import SalesRepresentative
from src.feat.sales_rep.infra.sales_rep_repos import SalesRepresentativesRepository
from src.feat.sales_rep.domain.sales_rep_excs import SalesRepresentativePhoneAlreadyExistsException

@pytest.mark.integration
async def test_add_duplicate_phone_raises_exception(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = SalesRepresentativesRepository(session=session)
        phone = "+79991234567"
        rep1 = SalesRepresentative.create(actor_id=uuid7(), name="Rep 1", phone=phone, commission_percent=10.0)
        await repository.add(rep1)
        await session.commit()
        
        rep2 = SalesRepresentative.create(actor_id=uuid7(), name="Rep 2", phone=phone, commission_percent=15.0)
        with pytest.raises(SalesRepresentativePhoneAlreadyExistsException) as exc:
            await repository.add(rep2)
        assert exc.value.phone == phone

@pytest.mark.integration
async def test_search_by_fuzzy_complex_logic(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = SalesRepresentativesRepository(session=session)
        # Контракт: name >= 0.35 И phone >= 0.50
        rep = SalesRepresentative.create(actor_id=uuid7(), name="Александр", phone="+79001112233", commission_percent=10.0)
        await repository.add(rep)
        await session.commit()
        
        # 1. Оба поля подходят
        res1 = await repository.search_by_fuzzy(name="Алекс", phone="+79001112234")
        assert res1 is not None
        
        # 2. Имя подходит, телефон нет (слишком разный)
        res2 = await repository.search_by_fuzzy(name="Алекс", phone="+70000000000")
        assert res2 is None
        
        # 3. Телефон подходит, имя нет
        res3 = await repository.search_by_fuzzy(name="Zzzzz", phone="+79001112233")
        assert res3 is None

@pytest.mark.integration
async def test_update_without_changes_does_nothing(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = SalesRepresentativesRepository(session=session)
        rep = SalesRepresentative.create(actor_id=uuid7(), name="No Change", phone="+79990000000", commission_percent=10.0)
        await repository.add(rep)
        await session.commit()
        
        sql_statements = []
        def before_cursor_execute(statement):
            sql_statements.append(statement)
            
        conn = await session.connection()
        event.listen(conn.sync_connection, "before_cursor_execute", before_cursor_execute)
        
        try:
            await repository.update(rep)
            assert not any("UPDATE" in stmt for stmt in sql_statements)
        finally:
            event.remove(conn.sync_connection, "before_cursor_execute", before_cursor_execute)
