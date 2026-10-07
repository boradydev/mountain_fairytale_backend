import pytest
from sqlalchemy import event
from src.core.uuid7 import uuid7
from src.feat.products.domain.product_entities import Product
from src.feat.products.infra.product_repos import ProductsRepository
from src.feat.products.domain.product_excs import ProductNameAlreadyExistsException

@pytest.mark.integration
async def test_add_duplicate_name_raises_exception(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = ProductsRepository(session=session)
        name = "Unique Product"
        p1 = Product.create(actor_id=uuid7(), name=name, base_price=100.0)
        await repository.add(p1)
        await session.commit()
        
        p2 = Product.create(actor_id=uuid7(), name=name, base_price=200.0)
        with pytest.raises(ProductNameAlreadyExistsException) as exc:
            await repository.add(p2)
        assert exc.value.name == name

@pytest.mark.integration
async def test_get_all_sorting(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = ProductsRepository(session=session)
        p1 = Product.create(actor_id=uuid7(), name="P1", base_price=10.0)
        p2 = Product.create(actor_id=uuid7(), name="P2", base_price=20.0)
        await repository.add(p1)
        await repository.add(p2)
        await session.commit()
        
        result = await repository.get_all(include_deactivated=True)
        # Проверка сортировки: created_at DESC, product_id DESC
        assert result[0].created_at >= result[1].created_at

@pytest.mark.integration
async def test_update_without_changes_does_nothing(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = ProductsRepository(session=session)
        product = Product.create(actor_id=uuid7(), name="No Change", base_price=10.0)
        await repository.add(product)
        await session.commit()
        
        sql_statements = []
        def before_cursor_execute(statement):
            sql_statements.append(statement)
            
        conn = await session.connection()
        event.listen(conn.sync_connection, "before_cursor_execute", before_cursor_execute)
        
        try:
            await repository.update(product)
            assert not any("UPDATE" in stmt for stmt in sql_statements)
        finally:
            event.remove(conn.sync_connection, "before_cursor_execute", before_cursor_execute)
