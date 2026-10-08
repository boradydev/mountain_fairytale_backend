import pytest

from src.core.uuid7 import uuid7
from src.feat.products.domain.product_entities import Product
from src.feat.products.domain.product_excs import ProductNameAlreadyExistsException
from src.feat.products.infra.product_repos import ProductsRepository
from tests.helpers import unique_product_name
from collections.abc import AsyncGenerator
from typing import Any


@pytest.fixture(autouse=True)
async def clean_products_table(postgres) -> AsyncGenerator[None, Any]:
    """Автоматически очищает таблицу продуктов перед каждым тестом в модуле."""
    await postgres.execute("TRUNCATE TABLE products RESTART IDENTITY CASCADE;")

    yield
    pass


@pytest.mark.integration
async def test_add_and_get_by_id(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = ProductsRepository(session=session)

        product = Product.create(
            actor_id=uuid7(),
            name=unique_product_name(),
            base_price=100.0,
        )

        await repository.add(product)
        await session.commit()

        result = await repository.get_by_id(product.product_id)

        assert result is not None
        assert result.product_id == product.product_id
        assert result.name == product.name
        assert result.base_price == 100.0
        assert result.is_active is True


@pytest.mark.integration
async def test_get_by_id_returns_none_for_unknown_product(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = ProductsRepository(session=session)

        result = await repository.get_by_id(uuid7())

        assert result is None


@pytest.mark.integration
async def test_get_all_excludes_deactivated_by_default(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = ProductsRepository(session=session)

        active = Product.create(
            actor_id=uuid7(),
            name=unique_product_name("active"),
            base_price=100.0,
        )
        inactive = Product.create(
            actor_id=uuid7(),
            name=unique_product_name("inactive"),
            base_price=200.0,
        )
        inactive.update(
            actor_id=uuid7(),
            is_active=False,
        )

        await repository.add(active)
        await repository.add(inactive)
        await session.commit()

        result = await repository.get_all(include_deactivated=False)

        assert {product.product_id for product in result} == {
            active.product_id,
        }


@pytest.mark.integration
async def test_get_all_includes_deactivated_when_requested(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = ProductsRepository(session=session)

        active = Product.create(
            actor_id=uuid7(),
            name=unique_product_name("active"),
            base_price=100.0,
        )
        inactive = Product.create(
            actor_id=uuid7(),
            name=unique_product_name("inactive"),
            base_price=200.0,
        )
        inactive.update(
            actor_id=uuid7(),
            is_active=False,
        )

        await repository.add(active)
        await repository.add(inactive)
        await session.commit()

        result = await repository.get_all(include_deactivated=True)

        assert {product.product_id for product in result} == {
            active.product_id,
            inactive.product_id,
        }


@pytest.mark.integration
async def test_update_persists_changes(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = ProductsRepository(session=session)

        product = Product.create(
            actor_id=uuid7(),
            name=unique_product_name(),
            base_price=100.0,
        )

        await repository.add(product)
        await session.commit()

        new_name = unique_product_name("updated")

        product.update(
            actor_id=uuid7(),
            name=new_name,
            base_price=250.0,
        )

        await repository.update(product)
        await session.commit()

        result = await repository.get_by_id(product.product_id)

        assert result is not None
        assert result.name == new_name
        assert result.base_price == 250.0


@pytest.mark.integration
async def test_add_duplicate_name_raises_exception(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = ProductsRepository(session=session)

        name = unique_product_name()

        first = Product.create(
            actor_id=uuid7(),
            name=name,
            base_price=100.0,
        )
        second = Product.create(
            actor_id=uuid7(),
            name=name,
            base_price=200.0,
        )

        await repository.add(first)
        await session.commit()

        with pytest.raises(ProductNameAlreadyExistsException) as exc_info:
            await repository.add(second)

        assert exc_info.value.name == name


@pytest.mark.integration
async def test_update_duplicate_name_raises_exception(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = ProductsRepository(session=session)

        first = Product.create(
            actor_id=uuid7(),
            name=unique_product_name("first"),
            base_price=100.0,
        )
        second = Product.create(
            actor_id=uuid7(),
            name=unique_product_name("second"),
            base_price=200.0,
        )

        await repository.add(first)
        await repository.add(second)
        await session.commit()

        # Сохраняем имя в обычную Python-строку ДО того, как упадет база данных.
        # Это защитит нас от PendingRollbackError при финальной проверке.
        expected_name = second.name

        first.update(
            actor_id=uuid7(),
            name=expected_name,
        )

        with pytest.raises(ProductNameAlreadyExistsException) as exc_info:
            await repository.update(first)

        # Сравниваем с сохраненной чистой строкой, не трогая заблокированный объект `second`
        assert exc_info.value.name == expected_name


@pytest.mark.integration
async def test_search_by_fuzzy_returns_match(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = ProductsRepository(session=session)

        product = Product.create(
            actor_id=uuid7(),
            name="Mountain Water",
            base_price=100.0,
        )

        await repository.add(product)
        await session.commit()

        result = await repository.search_by_fuzzy(
            name="Mountain Water",
        )

        assert result is not None
        assert result.product_id == product.product_id


@pytest.mark.integration
async def test_search_by_fuzzy_returns_none_without_match(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = ProductsRepository(session=session)

        product = Product.create(
            actor_id=uuid7(),
            name="Mountain Water",
            base_price=100.0,
        )

        await repository.add(product)
        await session.commit()

        result = await repository.search_by_fuzzy(
            name="Completely Different Product",
        )

        assert result is None
