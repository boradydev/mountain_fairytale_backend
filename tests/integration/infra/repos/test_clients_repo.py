from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.uuid7 import uuid7
from src.feat.clients.domain.client_entities import Client
from src.feat.clients.domain.client_excs import (
    ClientPhoneAlreadyExistsException,
    ClientRelatedEntityNotFoundException,
)
from src.feat.clients.infra.client_repos import ClientsRepository
from src.feat.pay_methods.domain.pay_method_entities import PaymentMethod
from src.feat.pay_methods.infra.pay_method_repos import PaymentMethodsRepository
from src.feat.sales_rep.domain.sales_rep_entities import SalesRepresentative
from src.feat.sales_rep.infra.sales_rep_repos import SalesRepresentativesRepository
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
async def test_get_by_id_returns_deactivated_client(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = ClientsRepository(session=session)
        client = await _create_client(repository)
        client.update(actor_id=uuid7(), is_active=False)
        await repository.update(client)
        await session.commit()

        result = await repository.get_by_id(client.client_id)

        assert result is not None
        assert result.client_id == client.client_id
        assert result.is_active is False


@pytest.mark.integration
async def test_unique_phone_raises_domain_exception(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = ClientsRepository(session=session)
        await _create_client(repository, phone="unique-client-phone")
        await session.commit()

        with pytest.raises(ClientPhoneAlreadyExistsException):
            await _create_client(repository, phone="unique-client-phone")


@pytest.mark.integration
async def test_update_with_own_phone_succeeds(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = ClientsRepository(session=session)
        client = await _create_client(repository)
        phone = client.phone

        client.update(actor_id=uuid7(), phone=phone)
        await repository.update(client)
        await session.commit()

        result = await repository.get_by_id(client.client_id)

        assert result is not None
        assert result.phone == phone


@pytest.mark.integration
async def test_update_with_another_clients_phone_raises_exception(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = ClientsRepository(session=session)
        first = await _create_client(repository)
        second = await _create_client(repository)
        await session.commit()

        first.update(actor_id=uuid7(), phone=second.phone)

        with pytest.raises(ClientPhoneAlreadyExistsException):
            await repository.update(first)


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
async def test_get_all_sorts_by_client_id_and_returns_total_for_empty_page(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = ClientsRepository(session=session)
        created_at = datetime.now()
        clients = []

        for index in range(3):
            client = await _create_client(repository, name=f"Client {index}")
            client.created_at = created_at
            clients.append(client)

        await session.commit()

        page, total = await repository.get_all(
            include_deactivated=True,
            offset=0,
            limit=10,
        )
        expected_ids = sorted(
            (client.client_id for client in clients),
            reverse=True,
        )

        assert [client.client_id for client in page] == expected_ids
        assert total == len(clients)

        next_page, next_total = await repository.get_all(
            include_deactivated=True,
            offset=len(clients),
            limit=10,
        )

        assert next_page == []
        assert next_total == total


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


@pytest.mark.integration
async def test_search_duplicate_finds_deactivated_client_with_two_matching_fields(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = ClientsRepository(session=session)
        client = await _create_client(
            repository,
            name="Matching Client",
            phone=unique_phone(),
            address="Original address",
        )
        client.update(actor_id=uuid7(), is_active=False)
        await repository.update(client)
        await session.commit()

        result = await repository.search_duplicate(
            name=client.name,
            phone=client.phone,
            address="Completely different address",
        )

        assert result is not None
        assert result.client_id == client.client_id
        assert result.is_active is False


@pytest.mark.integration
async def test_create_and_get_client_with_deactivated_related_entities(postgres) -> None:
    async with postgres.session_factory() as session:
        representative = await _create_sales_representative(
            session,
            name="Deactivated Representative",
        )
        representative.update(actor_id=uuid7(), is_active=False)
        await SalesRepresentativesRepository(session).update(representative)

        method = await _create_payment_method(
            session,
            name=f"Deactivated Payment Method {uuid7()}",
        )
        method.update(actor_id=uuid7(), is_active=False)
        await PaymentMethodsRepository(session).update(method)

        repository = ClientsRepository(session=session)
        client = await _create_client(
            repository,
            sales_representative_id=representative.sales_representative_id,
            default_payment_method_id=method.payment_method_id,
        )
        await session.commit()

    async with postgres.session_factory() as session:
        result = await ClientsRepository(session=session).get_by_id(client.client_id)

        assert result is not None
        assert result.sales_representative_id == representative.sales_representative_id
        assert result.default_payment_method_id == method.payment_method_id
        assert result.sales_representative_name == representative.name
        assert result.default_payment_method_name == method.name


@pytest.mark.integration
async def test_update_and_clear_related_entities(postgres) -> None:
    async with postgres.session_factory() as session:
        first_representative = await _create_sales_representative(
            session,
            name="First Representative",
        )
        second_representative = await _create_sales_representative(
            session,
            name="Second Representative",
        )
        first_method = await _create_payment_method(
            session,
            name=f"First Payment Method {uuid7()}",
        )
        second_method = await _create_payment_method(
            session,
            name=f"Second Payment Method {uuid7()}",
        )

        repository = ClientsRepository(session=session)
        client = await _create_client(
            repository,
            sales_representative_id=first_representative.sales_representative_id,
            default_payment_method_id=first_method.payment_method_id,
        )
        await session.commit()

        client.update(
            actor_id=uuid7(),
            sales_representative_id=second_representative.sales_representative_id,
            default_payment_method_id=second_method.payment_method_id,
        )
        await repository.update(client)
        await session.commit()
        client_id = client.client_id

    async with postgres.session_factory() as session:
        result = await ClientsRepository(session=session).get_by_id(client_id)

        assert result is not None
        assert result.sales_representative_id == second_representative.sales_representative_id
        assert result.default_payment_method_id == second_method.payment_method_id
        assert result.sales_representative_name == second_representative.name
        assert result.default_payment_method_name == second_method.name

    async with postgres.session_factory() as session:
        repository = ClientsRepository(session=session)
        client = await repository.get_by_id(client_id)

        assert client is not None
        client.update(
            actor_id=uuid7(),
            sales_representative_id=None,
            default_payment_method_id=None,
        )
        await repository.update(client)
        await session.commit()

    async with postgres.session_factory() as session:
        result = await ClientsRepository(session=session).get_by_id(client_id)

        assert result is not None
        assert result.sales_representative_id is None
        assert result.default_payment_method_id is None
        assert result.sales_representative_name is None
        assert result.default_payment_method_name is None


@pytest.mark.integration
@pytest.mark.parametrize(
    ("field", "entity_id_field"),
    [
        ("sales_representative_id", "sales_representative_id"),
        ("default_payment_method_id", "payment_method_id"),
    ],
)
async def test_add_with_missing_related_entity_raises_exception(
    postgres,
    field: str,
    entity_id_field: str,
) -> None:
    async with postgres.session_factory() as session:
        repository = ClientsRepository(session=session)
        missing_entity = {entity_id_field: uuid7()}
        missing_entity_id = missing_entity[entity_id_field]

        with pytest.raises(ClientRelatedEntityNotFoundException) as exc_info:
            await _create_client(
                repository,
                **{field: missing_entity_id},
            )

        assert exc_info.value.field == field
        assert exc_info.value.entity_id == missing_entity[entity_id_field]


@pytest.mark.integration
@pytest.mark.parametrize(
    ("field", "entity_id_field"),
    [
        ("sales_representative_id", "sales_representative_id"),
        ("default_payment_method_id", "payment_method_id"),
    ],
)
async def test_update_with_missing_related_entity_raises_exception(
    postgres,
    field: str,
    entity_id_field: str,
) -> None:
    async with postgres.session_factory() as session:
        repository = ClientsRepository(session=session)
        client = await _create_client(repository)
        await session.commit()

        missing_entity = {entity_id_field: uuid7()}
        missing_entity_id = missing_entity[entity_id_field]
        client.update(
            actor_id=uuid7(),
            **{field: missing_entity_id},
        )

        with pytest.raises(ClientRelatedEntityNotFoundException) as exc_info:
            await repository.update(client)

        assert exc_info.value.field == field
        assert exc_info.value.entity_id == missing_entity[entity_id_field]


async def _create_client(
    repository: ClientsRepository,
    *,
    name: str = "Client Example",
    phone: str | None = None,
    address: str = "Example address",
    sales_representative_id: Any = None,
    default_payment_method_id: Any = None,
) -> Client:
    client = Client.create(
        actor_id=uuid7(),
        name=name,
        phone=phone or uuid4().hex,
        address=address,
        sleeping_threshold_days=30,
        sales_representative_id=sales_representative_id,
        default_payment_method_id=default_payment_method_id,
    )
    await repository.add(client)
    return client


async def _create_sales_representative(
    session: AsyncSession,
    *,
    name: str,
) -> SalesRepresentative:
    representative = SalesRepresentative.create(
        actor_id=uuid7(),
        name=name,
        phone=unique_phone(),
        commission_percent=10.0,
    )
    await SalesRepresentativesRepository(session).add(representative)
    return representative


async def _create_payment_method(
    session: AsyncSession,
    *,
    name: str,
) -> PaymentMethod:
    method = PaymentMethod.create(actor_id=uuid7(), name=name)
    await PaymentMethodsRepository(session).add(method)
    return method
