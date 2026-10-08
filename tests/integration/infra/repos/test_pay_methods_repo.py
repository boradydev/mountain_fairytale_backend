from collections.abc import AsyncGenerator
from typing import Any

import pytest

from src.core.uuid7 import uuid7
from src.feat.pay_methods.domain.pay_method_entities import PaymentMethod
from src.feat.pay_methods.domain.pay_method_excs import PaymentMethodNameAlreadyExistsException
from src.feat.pay_methods.infra.pay_method_repos import PaymentMethodsRepository


@pytest.fixture(autouse=True)
async def clean_payment_methods_table(postgres) -> AsyncGenerator[None, Any]:
    """Автоматически очищает таблицу событий перед каждым тестом в модуле."""
    await postgres.execute("TRUNCATE TABLE payment_methods RESTART IDENTITY CASCADE;")

    yield
    pass


@pytest.mark.integration
async def test_add_and_get_by_id(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = PaymentMethodsRepository(session=session)

        method = PaymentMethod.create(
            actor_id=uuid7(),
            name="Cash",
        )

        await repository.add(method)
        await session.commit()

        result = await repository.get_by_id(method.payment_method_id)

        assert result is not None
        assert result.payment_method_id == method.payment_method_id
        assert result.name == "Cash"
        assert result.is_active is True


@pytest.mark.integration
async def test_get_by_id_returns_none_for_unknown_payment_method(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = PaymentMethodsRepository(session=session)

        result = await repository.get_by_id(uuid7())

        assert result is None


@pytest.mark.integration
async def test_get_all_excludes_deactivated_by_default(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = PaymentMethodsRepository(session=session)

        active = PaymentMethod.create(
            actor_id=uuid7(),
            name="Cash",
        )
        inactive = PaymentMethod.create(
            actor_id=uuid7(),
            name="Bank Transfer",
        )
        inactive.update(
            actor_id=uuid7(),
            is_active=False,
        )

        await repository.add(active)
        await repository.add(inactive)
        await session.commit()

        result = await repository.get_all(include_deactivated=False)

        assert {method.payment_method_id for method in result} == {
            active.payment_method_id,
        }


@pytest.mark.integration
async def test_get_all_includes_deactivated_when_requested(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = PaymentMethodsRepository(session=session)

        active = PaymentMethod.create(
            actor_id=uuid7(),
            name="Cash",
        )
        inactive = PaymentMethod.create(
            actor_id=uuid7(),
            name="Bank Transfer",
        )
        inactive.update(
            actor_id=uuid7(),
            is_active=False,
        )

        await repository.add(active)
        await repository.add(inactive)
        await session.commit()

        result = await repository.get_all(include_deactivated=True)

        assert {method.payment_method_id for method in result} == {
            active.payment_method_id,
            inactive.payment_method_id,
        }


@pytest.mark.integration
async def test_update_persists_changes(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = PaymentMethodsRepository(session=session)

        method = PaymentMethod.create(
            actor_id=uuid7(),
            name="Cash",
        )

        await repository.add(method)
        await session.commit()

        method.update(
            actor_id=uuid7(),
            name="Card",
        )

        await repository.update(method)
        await session.commit()

        result = await repository.get_by_id(method.payment_method_id)

        assert result is not None
        assert result.name == "Card"


@pytest.mark.integration
async def test_add_duplicate_name_raises_exception(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = PaymentMethodsRepository(session=session)

        first = PaymentMethod.create(
            actor_id=uuid7(),
            name="Cash",
        )
        second = PaymentMethod.create(
            actor_id=uuid7(),
            name="Cash",
        )

        await repository.add(first)
        await session.commit()

        with pytest.raises(PaymentMethodNameAlreadyExistsException):
            await repository.add(second)


@pytest.mark.integration
async def test_search_by_fuzzy_returns_match(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = PaymentMethodsRepository(session=session)

        method = PaymentMethod.create(
            actor_id=uuid7(),
            name="Credit Card",
        )

        await repository.add(method)
        await session.commit()

        result = await repository.search_by_fuzzy(
            name="Credit Card",
        )

        assert result is not None
        assert result.payment_method_id == method.payment_method_id


@pytest.mark.integration
async def test_search_by_fuzzy_returns_none_without_match(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = PaymentMethodsRepository(session=session)

        method = PaymentMethod.create(
            actor_id=uuid7(),
            name="Credit Card",
        )

        await repository.add(method)
        await session.commit()

        result = await repository.search_by_fuzzy(
            name="Completely Different",
        )

        assert result is None
