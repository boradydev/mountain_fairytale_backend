from collections.abc import AsyncGenerator
from typing import Any

import pytest

from src.feat.clients.domain.client_excs import ClientPhoneAlreadyExistsException
from src.feat.clients.infra.client_repos import ClientsRepository
from tests.helpers import unique_phone


@pytest.fixture(autouse=True)
async def clean_clients_table(postgres) -> AsyncGenerator[None, Any]:
    await postgres.execute("TRUNCATE TABLE clients RESTART IDENTITY CASCADE;")
    yield


@pytest.mark.integration
async def test_add_and_get_by_id(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = ClientsRepository(session=session)
        client = await _create_client(repository)
        await session.commit()

        result = await repository.get_by_id(client.client_id)

        assert result is not None
        assert result.client_id == client.client_id
        assert result.last_delivery_date is None
        assert result.last_delivery_quantity is None


@pytest.mark.integration
async def test_unique_phone_raises_domain_exception(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = ClientsRepository(session=session)
        await _create_client(repository, phone="unique-client-phone")
        await session.commit()

        with pytest.raises(ClientPhoneAlreadyExistsException):
            await _create_client(repository, phone="unique-client-phone")


@pytest.mark.integration
async def test_get_all_filters_and_paginates(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = ClientsRepository(session=session)
        first = await _create_client(repository)
        second = await _create_client(repository)
        inactive = await _create_client(repository)
        inactive.update(actor_id=first.client_id, is_active=False)
        await repository.update(inactive)
        await session.commit()

        active_page, active_total = await repository.get_all(
            include_deactivated=False,
            offset=1,
            limit=1,
        )
        all_page, all_total = await repository.get_all(
            include_deactivated=True,
            offset=0,
            limit=10,
        )

        assert active_total == 2
        assert len(active_page) == 1
        assert all_total == 3
        assert len(all_page) == 3
        assert all_page[0].created_at >= all_page[-1].created_at
        assert second.client_id in {client.client_id for client in all_page}


@pytest.mark.integration
async def test_search_duplicate_returns_none_without_two_matching_fields(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = ClientsRepository(session=session)
        await _create_client(
            repository,
            name="Client exact",
            phone=unique_phone(),
            address="Remote address",
        )
        await session.commit()

        result = await repository.search_duplicate(
            name="Client exact",
            phone=unique_phone(),
            address="Entirely different address",
        )

        assert result is None


async def _create_client(
    repository: ClientsRepository,
    *,
    name: str = "Client Example",
    phone: str | None = None,
    address: str = "Example address",
):
    from uuid import uuid4

    from src.core.uuid7 import uuid7
    from src.feat.clients.domain.client_entities import Client

    client = Client.create(
        actor_id=uuid7(),
        name=name,
        phone=phone or uuid4().hex,
        address=address,
        sleeping_threshold_days=30,
    )
    await repository.add(client)
    return client
