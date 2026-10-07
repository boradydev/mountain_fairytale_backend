import pytest
from sqlalchemy import event
from src.core.uuid7 import uuid7
from src.feat.pay_methods.domain.pay_method_entities import PaymentMethod
from src.feat.pay_methods.infra.pay_method_repos import PaymentMethodsRepository
from src.feat.pay_methods.domain.pay_method_excs import PaymentMethodNameAlreadyExistsException

@pytest.mark.integration
async def test_add_duplicate_name_raises_exception(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = PaymentMethodsRepository(session=session)
        name = "Cash"
        p1 = PaymentMethod.create(actor_id=uuid7(), name=name)
        await repository.add(p1)
        await session.commit()
        
        p2 = PaymentMethod.create(actor_id=uuid7(), name=name)
        with pytest.raises(PaymentMethodNameAlreadyExistsException):
            await repository.add(p2)

@pytest.mark.integration
async def test_search_by_fuzzy(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = PaymentMethodsRepository(session=session)
        pm = PaymentMethod.create(actor_id=uuid7(), name="Credit Card")
        await repository.add(pm)
        await session.commit()
        
        # Похожее имя
        result = await repository.search_by_fuzzy(name="Credit Card")
        assert result is not None
        assert result.payment_method_id == pm.payment_method_id
        
        # Совсем другое имя
        result_none = await repository.search_by_fuzzy(name="Apple Pay")
        assert result_none is None

@pytest.mark.integration
async def test_update_without_changes_does_nothing(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = PaymentMethodsRepository(session=session)
        pm = PaymentMethod.create(actor_id=uuid7(), name="No Change")
        await repository.add(pm)
        await session.commit()
        
        sql_statements = []
        def before_cursor_execute(statement):
            sql_statements.append(statement)
            
        conn = await session.connection()
        event.listen(conn.sync_connection, "before_cursor_execute", before_cursor_execute)
        
        try:
            await repository.update(pm)
            assert not any("UPDATE" in stmt for stmt in sql_statements)
        finally:
            event.remove(conn.sync_connection, "before_cursor_execute", before_cursor_execute)
