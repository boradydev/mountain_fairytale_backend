from collections.abc import AsyncGenerator
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.core.uuid7 import uuid7
from src.feat.cars.domain.car_entities import Car
from src.feat.cars.infra.car_repos import CarsRepository
from src.feat.clients.domain.client_entities import Client
from src.feat.clients.infra.client_repos import ClientsRepository
from src.feat.delivery_document.api.delivery_document_schemas import (
    UpdateDeliveryRouteSheetReq,
    UpdatePickupSheetReq,
)
from src.feat.delivery_document.domain.delivery_document_entities import (
    DeliveryDocument,
    DocumentType,
    EditLock,
)
from src.feat.delivery_document.domain.delivery_document_excs import (
    DeliveryDocumentEditLockNotFoundException,
    DeliveryDocumentEditLockNotOwnedException,
    DeliveryDocumentLockedException,
    DeliveryDocumentPointClientAlreadyExistsException,
    DeliveryDocumentPointProductAlreadyExistsException,
    DeliveryDocumentRelatedEntityNotFoundException,
    DeliveryDocumentUpdateException,
)
from src.feat.delivery_document.infra.delivery_document_repos import (
    DeliveryDocumentsRepository,
)
from src.feat.drivers.domain.driver_entities import Driver
from src.feat.drivers.infra.driver_repos import DriversRepository
from src.feat.employees.domain.employee_entities import Employee
from src.feat.employees.infra.employee_repos import EmployeesRepository
from src.feat.products.domain.product_entities import Product
from src.feat.products.infra.product_repos import ProductsRepository
from tests.helpers import unique_car_number, unique_phone, unique_product_name, unique_username


@pytest.fixture(autouse=True)
async def clean_delivery_documents_table(postgres) -> AsyncGenerator[None, Any]:
    """Очищает документы доставки и связанные с ними таблицы перед каждым тестом."""
    await postgres.execute("TRUNCATE TABLE delivery_documents RESTART IDENTITY CASCADE;")
    yield


async def _create_related_entities(
    session,
    *,
    delivery: bool,
    client_count: int = 1,
) -> tuple[list[Client], Product, Driver | None, Car | None]:
    """Создаёт связанные сущности в той же сессии, что и тестируемый документ."""
    clients_repository = ClientsRepository(session=session)
    clients = [
        Client.create(
            actor_id=uuid7(),
            name=f"Тестовый клиент {uuid7()}",
            phone=unique_phone(),
            address=f"Тестовый адрес {uuid7()}",
            sleeping_threshold_days=30,
        )
        for _ in range(client_count)
    ]
    for client in clients:
        await clients_repository.add(client)

    product = Product.create(
        actor_id=uuid7(),
        name=unique_product_name("delivery_document"),
        base_price=125.5,
    )
    await ProductsRepository(session=session).add(product)

    driver: Driver | None = None
    car: Car | None = None
    if delivery:
        driver = Driver.create(actor_id=uuid7(), name=f"Водитель {uuid7()}")
        car = Car.create(
            actor_id=uuid7(),
            model="Тестовый автомобиль",
            number=unique_car_number(),
            current_mileage=100.0,
        )
        if driver is None or car is None:
            raise ValueError

        await DriversRepository(session=session).add(driver)
        await CarsRepository(session=session).add(car)

    return clients, product, driver, car


def _make_point(client_id, product_id, *, quantity: int, price: float) -> SimpleNamespace:
    return SimpleNamespace(
        client_id=client_id,
        items=[
            SimpleNamespace(
                product_id=product_id,
                quantity=quantity,
                price=price,
            ),
        ],
    )


async def _create_document(
    session,
    *,
    document_type: DocumentType,
    clients: list[Client],
    product: Product,
    driver: Driver | None = None,
    car: Car | None = None,
    quantities: list[int] | None = None,
) -> DeliveryDocument:
    quantities = quantities or [2] * len(clients)
    points = [
        _make_point(
            client.client_id,
            product.product_id,
            quantity=quantities[index],
            price=125.5 + index,
        )
        for index, client in enumerate(clients)
    ]
    return DeliveryDocument.create(
        actor_id=uuid7(),
        document_type=document_type,
        planned_date=date(2025, 3, 15),
        points=points,
        driver_id=driver.driver_id if driver is not None else None,
        car_id=car.car_id if car is not None else None,
        start_mileage=100.0 if document_type == DocumentType.DELIVERY else None,
    )


@pytest.mark.integration
async def test_add_and_get_by_id(postgres) -> None:
    async with postgres.session_factory() as session:
        clients, product, driver, car = await _create_related_entities(
            session,
            delivery=True,
            client_count=2,
        )
        document = await _create_document(
            session,
            document_type=DocumentType.DELIVERY,
            clients=clients,
            product=product,
            driver=driver,
            car=car,
            quantities=[3, 7],
        )
        repository = DeliveryDocumentsRepository(session=session)

        await repository.add(document)
        await session.commit()

        result = await repository.get_by_id(
            document.delivery_document_id,
            document_type=DocumentType.DELIVERY,
        )

        assert result is not None
        assert result.document_type == DocumentType.DELIVERY
        assert result.planned_date == date(2025, 3, 15)
        assert [point.position for point in result.points] == [0, 1]
        assert [point.client_id for point in result.points] == [
            client.client_id for client in clients
        ]
        assert [point.client_name for point in result.points] == [
            client.name for client in clients
        ]
        assert len(result.points[0].items) == 1
        assert result.points[0].items[0].product_id == product.product_id
        assert result.points[0].items[0].product_name == product.name
        assert result.points[0].items[0].quantity == 3
        assert result.points[0].items[0].price == 125.5
        assert result.points[1].items[0].quantity == 7
        assert result.points[1].items[0].price == 126.5

        wrong_type = await repository.get_by_id(
            document.delivery_document_id,
            document_type=DocumentType.PICKUP,
        )
        unknown_id = await repository.get_by_id(
            uuid7(),
            document_type=DocumentType.DELIVERY,
        )

        assert wrong_type is None
        assert unknown_id is None


@pytest.mark.integration
async def test_get_all_filters_by_type_cancelled_status_and_paginates(postgres) -> None:
    async with postgres.session_factory() as session:
        delivery_clients, delivery_product, driver, car = await _create_related_entities(
            session,
            delivery=True,
            client_count=3,
        )
        pickup_clients, pickup_product, _, _ = await _create_related_entities(
            session,
            delivery=False,
            client_count=1,
        )
        repository = DeliveryDocumentsRepository(session=session)

        active_delivery = await _create_document(
            session,
            document_type=DocumentType.DELIVERY,
            clients=[delivery_clients[0]],
            product=delivery_product,
            driver=driver,
            car=car,
        )
        cancelled_delivery = await _create_document(
            session,
            document_type=DocumentType.DELIVERY,
            clients=[delivery_clients[1]],
            product=delivery_product,
            driver=driver,
            car=car,
        )
        cancelled_delivery.cancel(actor_id=uuid7())
        active_pickup = await _create_document(
            session,
            document_type=DocumentType.PICKUP,
            clients=pickup_clients,
            product=pickup_product,
        )

        active_delivery.created_at = datetime(2025, 3, 15, 12, 0, 0)
        cancelled_delivery.created_at = active_delivery.created_at + timedelta(hours=1)

        await repository.add(active_delivery)
        await repository.add(cancelled_delivery)
        await repository.add(active_pickup)
        await session.commit()

        active_deliveries, active_delivery_total = await repository.get_all(
            document_type=DocumentType.DELIVERY,
            include_cancelled=False,
            offset=0,
            limit=10,
        )
        all_deliveries, all_delivery_total = await repository.get_all(
            document_type=DocumentType.DELIVERY,
            include_cancelled=True,
            offset=0,
            limit=10,
        )
        pickups, pickup_total = await repository.get_all(
            document_type=DocumentType.PICKUP,
            include_cancelled=True,
            offset=0,
            limit=10,
        )
        first_page, first_page_total = await repository.get_all(
            document_type=DocumentType.DELIVERY,
            include_cancelled=True,
            offset=0,
            limit=1,
        )
        second_page, second_page_total = await repository.get_all(
            document_type=DocumentType.DELIVERY,
            include_cancelled=True,
            offset=1,
            limit=1,
        )

        assert active_delivery_total == 1
        assert [document.delivery_document_id for document in active_deliveries] == [
            active_delivery.delivery_document_id,
        ]
        assert all_delivery_total == 2
        assert [document.delivery_document_id for document in all_deliveries] == [
            cancelled_delivery.delivery_document_id,
            active_delivery.delivery_document_id,
        ]
        assert pickup_total == 1
        assert [document.delivery_document_id for document in pickups] == [
            active_pickup.delivery_document_id,
        ]
        assert first_page_total == second_page_total == 2
        assert [document.delivery_document_id for document in first_page] == [
            cancelled_delivery.delivery_document_id,
        ]
        assert [document.delivery_document_id for document in second_page] == [
            active_delivery.delivery_document_id,
        ]


@pytest.mark.integration
async def test_update_persists_document_fields_and_point_order(postgres) -> None:
    async with postgres.session_factory() as session:
        clients, product, driver, car = await _create_related_entities(
            session,
            delivery=True,
            client_count=2,
        )
        document = await _create_document(
            session,
            document_type=DocumentType.DELIVERY,
            clients=clients,
            product=product,
            driver=driver,
            car=car,
        )
        repository = DeliveryDocumentsRepository(session=session)

        await repository.add(document)
        await session.commit()

        document.planned_date = date(2025, 4, 20)
        document.points[0].position = 1
        document.points[1].position = 0
        await repository.update(document)
        await session.commit()

        updated = await repository.get_by_id(
            document.delivery_document_id,
            document_type=DocumentType.DELIVERY,
        )

        assert updated is not None
        assert updated.planned_date == date(2025, 4, 20)
        assert [point.client_id for point in updated.points] == [
            clients[1].client_id,
            clients[0].client_id,
        ]
        assert [point.position for point in updated.points] == [0, 1]

        # Обновление корневых полей без изменений точек не должно портить документ.
        updated.end_mileage = 150.0
        await repository.update(updated)
        await session.commit()

        unchanged_points = await repository.get_by_id(
            document.delivery_document_id,
            document_type=DocumentType.DELIVERY,
        )

        assert unchanged_points is not None
        assert unchanged_points.end_mileage == 150.0
        assert [point.client_id for point in unchanged_points.points] == [
            clients[1].client_id,
            clients[0].client_id,
        ]


@pytest.mark.integration
async def test_edit_lock_acquire_renew_release_and_ownership(postgres) -> None:
    async with postgres.session_factory() as session:
        clients, product, driver, car = await _create_related_entities(
            session,
            delivery=True,
        )
        document = await _create_document(
            session,
            document_type=DocumentType.DELIVERY,
            clients=clients,
            product=product,
            driver=driver,
            car=car,
        )
        owner = Employee.create(
            actor_id=uuid7(),
            username=unique_username("lock_owner"),
            password_hash="test-password-hash",
            role="employee",
            commission_percent=0.0,
        )
        other_employee = Employee.create(
            actor_id=uuid7(),
            username=unique_username("lock_other"),
            password_hash="test-password-hash",
            role="employee",
            commission_percent=0.0,
        )
        repository = DeliveryDocumentsRepository(session=session)

        await EmployeesRepository(session=session).add(owner)
        await EmployeesRepository(session=session).add(other_employee)
        await repository.add(document)
        await session.commit()

        before = datetime.now()
        owner_name = await repository.acquire_edit_lock(
            delivery_document_id=document.delivery_document_id,
            employee_id=owner.employee_id,
        )
        after = datetime.now()
        assert owner_name == owner.username

        lock_expiration = await session.execute(
            select(EditLock.expires_at).where(
                EditLock.delivery_document_id == document.delivery_document_id,
            ),
        )
        expires_at = lock_expiration.scalar_one()
        assert before + EditLock.TTL <= expires_at <= after + EditLock.TTL

        repeated_owner_name = await repository.acquire_edit_lock(
            delivery_document_id=document.delivery_document_id,
            employee_id=owner.employee_id,
        )
        assert repeated_owner_name == owner.username

        renewed_owner_name = await repository.renew_edit_lock(
            delivery_document_id=document.delivery_document_id,
            employee_id=owner.employee_id,
        )
        assert renewed_owner_name == owner.username

        with pytest.raises(DeliveryDocumentLockedException):
            await repository.acquire_edit_lock(
                delivery_document_id=document.delivery_document_id,
                employee_id=other_employee.employee_id,
            )

        with pytest.raises(DeliveryDocumentEditLockNotOwnedException):
            await repository.release_edit_lock(
                delivery_document_id=document.delivery_document_id,
                employee_id=other_employee.employee_id,
            )

        await repository.release_edit_lock(
            delivery_document_id=document.delivery_document_id,
            employee_id=owner.employee_id,
        )

        with pytest.raises(DeliveryDocumentEditLockNotFoundException):
            await repository.release_edit_lock(
                delivery_document_id=document.delivery_document_id,
                employee_id=owner.employee_id,
            )

        with pytest.raises(DeliveryDocumentEditLockNotFoundException):
            await repository.renew_edit_lock(
                delivery_document_id=document.delivery_document_id,
                employee_id=owner.employee_id,
            )


@pytest.mark.integration
async def test_acquire_edit_lock_replaces_expired_lock(postgres) -> None:
    async with postgres.session_factory() as session:
        clients, product, driver, car = await _create_related_entities(
            session,
            delivery=True,
        )
        document = await _create_document(
            session,
            document_type=DocumentType.DELIVERY,
            clients=clients,
            product=product,
            driver=driver,
            car=car,
        )
        owner = Employee.create(
            actor_id=uuid7(),
            username=unique_username("expired_lock_owner"),
            password_hash="test-password-hash",
            role="employee",
            commission_percent=0.0,
        )
        next_owner = Employee.create(
            actor_id=uuid7(),
            username=unique_username("expired_lock_next_owner"),
            password_hash="test-password-hash",
            role="employee",
            commission_percent=0.0,
        )
        repository = DeliveryDocumentsRepository(session=session)

        await EmployeesRepository(session=session).add(owner)
        await EmployeesRepository(session=session).add(next_owner)
        await repository.add(document)
        await session.commit()

        session.add(
            EditLock.create(
                delivery_document_id=document.delivery_document_id,
                employee_id=owner.employee_id,
                expires_at=datetime.now() - EditLock.TTL - timedelta(seconds=1),
            ),
        )
        await session.commit()

        owner_name = await repository.acquire_edit_lock(
            delivery_document_id=document.delivery_document_id,
            employee_id=next_owner.employee_id,
        )

        assert owner_name == next_owner.username

        lock_result = await session.execute(
            select(EditLock.employee_id, EditLock.expires_at).where(
                EditLock.delivery_document_id == document.delivery_document_id,
            ),
        )
        saved_employee_id, saved_expires_at = lock_result.one()
        assert saved_employee_id == next_owner.employee_id
        assert saved_expires_at > datetime.now()


@pytest.mark.integration
@pytest.mark.parametrize(
    ("missing_reference", "expected_field"),
    [
        ("client", "client_id"),
        ("product", "product_id"),
    ],
)
async def test_validate_references_rejects_missing_entities(
    postgres,
    missing_reference: str,
    expected_field: str,
) -> None:
    async with postgres.session_factory() as session:
        clients, product, _, _ = await _create_related_entities(
            session,
            delivery=False,
        )
        client_id = uuid7() if missing_reference == "client" else clients[0].client_id
        product_id = uuid7() if missing_reference == "product" else product.product_id
        document = DeliveryDocument.create(
            actor_id=uuid7(),
            document_type=DocumentType.PICKUP,
            planned_date=date(2025, 3, 15),
            points=[
                SimpleNamespace(
                    client_id=client_id,
                    items=[
                        SimpleNamespace(
                            product_id=product_id,
                            quantity=1,
                            price=10.0,
                        ),
                    ],
                ),
            ],
        )
        repository = DeliveryDocumentsRepository(session=session)

        with pytest.raises(DeliveryDocumentRelatedEntityNotFoundException) as exc_info:
            await repository.validate_references(document)

        assert exc_info.value.field == expected_field


@pytest.mark.integration
@pytest.mark.parametrize("missing_field", ["driver_id", "car_id"])
async def test_validate_active_assignments_rejects_missing_transport_entities(
    postgres,
    missing_field: str,
) -> None:
    async with postgres.session_factory() as session:
        _, _, driver, car = await _create_related_entities(session, delivery=True)
        assert driver is not None
        assert car is not None

        driver_id = uuid7() if missing_field == "driver_id" else driver.driver_id
        car_id = uuid7() if missing_field == "car_id" else car.car_id
        repository = DeliveryDocumentsRepository(session=session)

        with pytest.raises(DeliveryDocumentRelatedEntityNotFoundException) as exc_info:
            await repository.validate_active_assignments(
                document_type=DocumentType.DELIVERY,
                planned_date=date(2025, 3, 15),
                driver_id=driver_id,
                car_id=car_id,
            )

        assert exc_info.value.field == missing_field


@pytest.mark.integration
async def test_pickup_sheet_persists_null_transport_fields(postgres) -> None:
    async with postgres.session_factory() as session:
        clients, product, _, _ = await _create_related_entities(session, delivery=False)
        repository = DeliveryDocumentsRepository(session=session)
        document = await _create_document(
            session,
            document_type=DocumentType.PICKUP,
            clients=clients,
            product=product,
        )

        await repository.add(document)
        await session.commit()

        saved = await repository.get_by_id(
            document.delivery_document_id,
            document_type=DocumentType.PICKUP,
        )
        assert saved is not None
        assert saved.driver_id is None
        assert saved.car_id is None
        assert saved.start_mileage is None
        assert saved.end_mileage is None


@pytest.mark.integration
@pytest.mark.parametrize("invalid_end_mileage", [50.0, 100.0])
async def test_delivery_mileage_validation_on_update(
    postgres,
    invalid_end_mileage: float,
) -> None:
    async with postgres.session_factory() as session:
        clients, product, driver, car = await _create_related_entities(session, delivery=True)
        repository = DeliveryDocumentsRepository(session=session)

        document = await _create_document(
            session,
            document_type=DocumentType.DELIVERY,
            clients=clients,
            product=product,
            driver=driver,
            car=car,
        )
        await repository.add(document)
        await session.commit()

        document.update(
            actor_id=uuid7(),
            request=UpdateDeliveryRouteSheetReq(end_mileage=None),
        )
        await repository.update(document)
        await session.commit()

        document.update(
            actor_id=uuid7(),
            request=UpdateDeliveryRouteSheetReq(end_mileage=200.0),
        )
        await repository.update(document)
        await session.commit()

        updated = await repository.get_by_id(
            document.delivery_document_id,
            document_type=DocumentType.DELIVERY,
        )
        assert updated is not None
        assert updated.end_mileage == 200.0

        with pytest.raises(DeliveryDocumentUpdateException) as exc_info:
            document.update(
                actor_id=uuid7(),
                request=UpdateDeliveryRouteSheetReq(end_mileage=invalid_end_mileage),
            )

        assert exc_info.value.field == "end_mileage"


@pytest.mark.integration
@pytest.mark.parametrize("invalid_end_mileage", [50.0, 100.0])
async def test_delivery_mileage_validation_on_create(
    postgres,
    invalid_end_mileage: float,
) -> None:
    async with postgres.session_factory() as session:
        clients, product, driver, car = await _create_related_entities(session, delivery=True)
        assert driver is not None
        assert car is not None

        with pytest.raises(DeliveryDocumentUpdateException) as exc_info:
            DeliveryDocument.create(
                actor_id=uuid7(),
                document_type=DocumentType.DELIVERY,
                planned_date=date(2025, 3, 15),
                points=[
                    _make_point(
                        clients[0].client_id,
                        product.product_id,
                        quantity=1,
                        price=10.0,
                    ),
                ],
                driver_id=driver.driver_id,
                car_id=car.car_id,
                start_mileage=100.0,
                end_mileage=invalid_end_mileage,
            )

        assert exc_info.value.field == "end_mileage"


@pytest.mark.integration
async def test_duplicate_client_in_same_document_is_forbidden(postgres) -> None:
    async with postgres.session_factory() as session:
        clients, product, driver, car = await _create_related_entities(
            session,
            delivery=True,
            client_count=1,
        )
        repository = DeliveryDocumentsRepository(session=session)

        points = [
            _make_point(clients[0].client_id, product.product_id, quantity=2, price=10.0),
            _make_point(clients[0].client_id, product.product_id, quantity=5, price=15.0),
        ]

        document = DeliveryDocument.create(
            actor_id=uuid7(),
            document_type=DocumentType.DELIVERY,
            planned_date=date(2025, 3, 15),
            points=points,
            driver_id=driver.driver_id,
            car_id=car.car_id,
            start_mileage=100.0,
        )

        with pytest.raises(DeliveryDocumentPointClientAlreadyExistsException) as exc_info:
            await repository.add(document)

        assert isinstance(exc_info.value.__cause__, IntegrityError)


@pytest.mark.integration
async def test_duplicate_product_in_same_point_is_forbidden(postgres) -> None:
    async with postgres.session_factory() as session:
        clients, product, _, _ = await _create_related_entities(
            session,
            delivery=False,
        )
        duplicate_item = SimpleNamespace(
            product_id=product.product_id,
            quantity=1,
            price=10.0,
        )
        document = DeliveryDocument.create(
            actor_id=uuid7(),
            document_type=DocumentType.PICKUP,
            planned_date=date(2025, 3, 15),
            points=[
                SimpleNamespace(
                    client_id=clients[0].client_id,
                    items=[duplicate_item, duplicate_item],
                ),
            ],
        )

        with pytest.raises(DeliveryDocumentPointProductAlreadyExistsException) as exc_info:
            await DeliveryDocumentsRepository(session=session).add(document)

        assert isinstance(exc_info.value.__cause__, IntegrityError)


@pytest.mark.integration
async def test_cascade_delete_points_and_items(postgres) -> None:
    """Проверяет разрешённую контрактом очистку точек через PATCH."""
    async with postgres.session_factory() as session:
        clients, product, driver, car = await _create_related_entities(session, delivery=True, client_count=2)
        repository = DeliveryDocumentsRepository(session=session)

        document = await _create_document(
            session,
            document_type=DocumentType.DELIVERY,
            clients=clients,
            product=product,
            driver=driver,
            car=car,
        )
        await repository.add(document)
        await session.commit()

        initial_check = await repository.get_by_id(
            document.delivery_document_id,
            document_type=DocumentType.DELIVERY,
        )
        assert initial_check is not None
        assert len(initial_check.points) == 2

        document.update(
            actor_id=uuid7(),
            request=UpdatePickupSheetReq(points=[]),
        )
        await repository.update(document)
        await session.commit()

        updated = await repository.get_by_id(
            document.delivery_document_id,
            document_type=DocumentType.DELIVERY,
        )
        assert updated is not None
        assert len(updated.points) == 0
