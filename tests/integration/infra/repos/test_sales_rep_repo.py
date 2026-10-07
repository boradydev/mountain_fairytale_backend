import pytest

from src.core.uuid7 import uuid7
from src.feat.sales_rep.domain.sales_rep_entities import SalesRepresentative
from src.feat.sales_rep.domain.sales_rep_excs import SalesRepresentativePhoneAlreadyExistsException
from src.feat.sales_rep.infra.sales_rep_repos import SalesRepresentativesRepository
from tests.helpers import unique_phone


def make_sales_rep(
    *,
    name: str,
    phone: str | None = None,
    commission_percent: float = 10.0,
) -> SalesRepresentative:
    return SalesRepresentative.create(
        actor_id=uuid7(),
        name=name,
        phone=phone or unique_phone(),
        commission_percent=commission_percent,
    )


@pytest.mark.integration
async def test_add_and_get_by_id(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = SalesRepresentativesRepository(session=session)

        rep = make_sales_rep(
            name="Alexander",
            commission_percent=12.5,
        )

        await repository.add(rep)
        await session.commit()

        result = await repository.get_by_id(rep.sales_representative_id)

        assert result is not None
        assert result.sales_representative_id == rep.sales_representative_id
        assert result.name == "Alexander"
        assert result.phone == rep.phone
        assert result.commission_percent == 12.5
        assert result.is_active is True


@pytest.mark.integration
async def test_get_by_id_returns_none_for_unknown_sales_rep(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = SalesRepresentativesRepository(session=session)

        result = await repository.get_by_id(uuid7())

        assert result is None


@pytest.mark.integration
async def test_get_by_phone(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = SalesRepresentativesRepository(session=session)

        phone = unique_phone()
        rep = make_sales_rep(
            name="Alexander",
            phone=phone,
        )

        await repository.add(rep)
        await session.commit()

        result = await repository.get_by_phone(phone)

        assert result is not None
        assert result.sales_representative_id == rep.sales_representative_id
        assert result.phone == phone


@pytest.mark.integration
async def test_get_by_phone_returns_none_for_unknown_phone(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = SalesRepresentativesRepository(session=session)

        result = await repository.get_by_phone(unique_phone())

        assert result is None


@pytest.mark.integration
async def test_get_all_excludes_deactivated_by_default(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = SalesRepresentativesRepository(session=session)

        active = make_sales_rep(name="Active")
        inactive = make_sales_rep(name="Inactive")
        inactive.update(
            actor_id=uuid7(),
            is_active=False,
        )

        await repository.add(active)
        await repository.add(inactive)
        await session.commit()

        result = await repository.get_all(include_deactivated=False)

        assert {rep.sales_representative_id for rep in result} == {
            active.sales_representative_id,
        }


@pytest.mark.integration
async def test_get_all_includes_deactivated_when_requested(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = SalesRepresentativesRepository(session=session)

        active = make_sales_rep(name="Active")
        inactive = make_sales_rep(name="Inactive")
        inactive.update(
            actor_id=uuid7(),
            is_active=False,
        )

        await repository.add(active)
        await repository.add(inactive)
        await session.commit()

        result = await repository.get_all(include_deactivated=True)

        assert {rep.sales_representative_id for rep in result} == {
            active.sales_representative_id,
            inactive.sales_representative_id,
        }


@pytest.mark.integration
async def test_update_persists_changes(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = SalesRepresentativesRepository(session=session)

        rep = make_sales_rep(
            name="Old Name",
            commission_percent=10.0,
        )

        await repository.add(rep)
        await session.commit()

        new_phone = unique_phone()

        rep.update(
            actor_id=uuid7(),
            name="New Name",
            phone=new_phone,
            commission_percent=15.0,
        )

        await repository.update(rep)
        await session.commit()

        result = await repository.get_by_id(rep.sales_representative_id)

        assert result is not None
        assert result.name == "New Name"
        assert result.phone == new_phone
        assert result.commission_percent == 15.0


@pytest.mark.integration
async def test_add_duplicate_phone_raises_exception(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = SalesRepresentativesRepository(session=session)

        phone = unique_phone()

        first = make_sales_rep(
            name="First",
            phone=phone,
        )
        second = make_sales_rep(
            name="Second",
            phone=phone,
        )

        await repository.add(first)
        await session.commit()

        with pytest.raises(SalesRepresentativePhoneAlreadyExistsException) as exc_info:
            await repository.add(second)

        assert exc_info.value.phone == phone


@pytest.mark.integration
async def test_update_duplicate_phone_raises_exception(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = SalesRepresentativesRepository(session=session)

        first = make_sales_rep(name="First")
        second = make_sales_rep(name="Second")

        await repository.add(first)
        await repository.add(second)
        await session.commit()

        first.update(
            actor_id=uuid7(),
            phone=second.phone,
        )

        with pytest.raises(SalesRepresentativePhoneAlreadyExistsException) as exc_info:
            await repository.update(first)

        assert exc_info.value.phone == second.phone


@pytest.mark.integration
async def test_search_by_fuzzy_returns_match(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = SalesRepresentativesRepository(session=session)

        rep = make_sales_rep(
            name="Alexander",
            phone="79001234567",
        )

        await repository.add(rep)
        await session.commit()

        result = await repository.search_by_fuzzy(
            name="Alexander",
            phone="79001234567",
        )

        assert result is not None
        assert result.sales_representative_id == rep.sales_representative_id


@pytest.mark.integration
async def test_search_by_fuzzy_returns_none_without_match(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = SalesRepresentativesRepository(session=session)

        rep = make_sales_rep(
            name="Alexander",
            phone="79001234567",
        )

        await repository.add(rep)
        await session.commit()

        result = await repository.search_by_fuzzy(
            name="Completely Different",
            phone="79999999999",
        )

        assert result is None
