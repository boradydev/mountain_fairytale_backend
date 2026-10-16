from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from src.core.uuid7 import uuid7
from tests.helpers import unique_car_number, unique_phone, unique_product_name
from tests.integration.api.test_delivery_document_routers import (
    DELIVERY_BASE_PATH,
    PICKUP_BASE_PATH,
    TestDeliveryDocumentRouters as DeliveryAPI,
)


BASE = "/protected/delivery-days"


@pytest.fixture(autouse=True)
async def clean_documents(postgres) -> None:
    """Isolate calendar boundaries from documents created by other tests."""
    await postgres.execute("TRUNCATE TABLE delivery_documents CASCADE")


@dataclass
class DaysCase:
    client: AsyncClient
    today: date
    customer_ids: list[str]
    product_ids: list[str]
    driver_id: str
    car_id: str

    async def create(self, day: date, *, delivery: bool = False, points=None) -> dict[str, Any]:
        payload = {"plannedDate": day.isoformat(), "points": points or []}
        base = DELIVERY_BASE_PATH if delivery else PICKUP_BASE_PATH
        if delivery:
            payload.update(driverId=self.driver_id, carId=self.car_id, startMileage=100.0)
        response = await self.client.post(f"{base}/create", json=payload)
        assert response.status_code == 201, response.text
        return response.json()["data"]

    def point(self, *, customer: int = 0, product: int = 0, name="Вода", quantity=1, price=1.005):
        return DeliveryAPI.point_payload(
            self.customer_ids[customer],
            self.product_ids[product],
            product_name=name,
            quantity=quantity,
            price=price,
        )

    def path(self, document):
        base = DELIVERY_BASE_PATH if "driverId" in document else PICKUP_BASE_PATH
        return f"{base}/{document['deliveryDocumentId']}"

    async def days(self, **params):
        response = await self.client.get(BASE, params=params)
        assert response.status_code == 200, response.text
        return response.json()

    async def documents(self, day, **params):
        response = await self.client.get(f"{BASE}/{day}/documents", params=params)
        assert response.status_code == 200, response.text
        return response.json()


@pytest.fixture
async def case(client, active_employee, postgres) -> DaysCase:
    await DeliveryAPI.login(client, active_employee)
    async with postgres.session_factory() as session:
        today = (await session.execute(text("SELECT CURRENT_DATE"))).scalar_one()
    customer_ids = []
    for _ in range(2):
        response = await client.post(
            "/protected/clients/create",
            json={
                "name": f"Day client {uuid7()}",
                "phone": unique_phone(),
                "address": "Адрес",
                "sleepingThresholdDays": 10,
            },
        )
        assert response.status_code == 201
        customer_ids.append(response.json()["data"]["clientId"])
    product_ids = []
    for _ in range(3):
        product = await DeliveryAPI.create_product(client, unique_product_name("days"))
        product_ids.append(product["productId"])
    driver = await DeliveryAPI.create_driver(client, f"Day driver {uuid7()}")
    response = await client.post("/protected/cars/create", json={"model": "Day car", "number": unique_car_number()})
    assert response.status_code == 201
    return DaysCase(client, today, customer_ids, product_ids, driver["driverId"], response.json()["data"]["carId"])


def empty_card(day: date) -> dict[str, Any]:
    return {
        "plannedDate": day.isoformat(),
        "deliveryPointsCount": 0,
        "pickupPointsCount": 0,
        "products": [],
        "totalAmount": 0,
    }


@pytest.mark.parametrize("path", [BASE, f"{BASE}/2026-10-13/documents"])
async def test_days_require_authentication(client, path):
    response = await client.get(path)
    assert response.status_code == 401


@pytest.mark.parametrize(
    "path",
    [
        f"{BASE}?offset=-1",
        f"{BASE}?limit=0",
        f"{BASE}?limit=abc",
        f"{BASE}/2026-02-30/documents",
        f"{BASE}/bad-date/documents",
        f"{BASE}/2026-10-13/documents?include_cancelled=invalid",
    ],
)
async def test_invalid_day_parameters(case, path):
    assert (await case.client.get(path)).status_code == 422


async def test_no_documents_means_no_calendar(case):
    body = await case.days()
    assert (body["offset"], body["limit"], body["total"], body["data"]) == (0, 100, 0, {"deliveryDays": []})
    assert (await case.days(offset=100, limit=3))["total"] == 0
    body = await case.documents(case.today)
    assert body["data"] == {"documents": []}
    assert body["total"] == 0
    assert body["offset"] is None
    assert body["limit"] is None


async def test_calendar_pages_include_gaps_and_cancelled_boundaries(case):
    earliest = case.today - timedelta(days=4)
    latest = case.today + timedelta(days=3)
    first = await case.create(earliest)
    last = await case.create(latest, delivery=True)
    for document in (first, last):
        assert (await case.client.post(f"{case.path(document)}/cancel")).status_code == 200
    body = await case.days(limit=3)
    assert body["total"] == 8
    assert body["data"]["deliveryDays"] == [empty_card(latest - timedelta(days=i)) for i in range(3)]
    second = await case.days(offset=3, limit=10)
    assert second["total"] == 8
    assert second["data"]["deliveryDays"] == [empty_card(latest - timedelta(days=i)) for i in range(3, 8)]
    for offset in (8, 100):
        beyond = await case.days(offset=offset, limit=2)
        assert beyond["total"] == 8
        assert beyond["data"] == {"deliveryDays": []}


async def test_today_extends_past_documents_and_future_only_starts_in_future(case):
    day = case.today + timedelta(days=5)
    document = await case.create(day)
    body = await case.days()
    assert body["total"] == 1
    assert body["data"]["deliveryDays"] == [empty_card(day)]
    path = case.path(document)
    assert (await case.client.post(f"{path}/edit-lock")).status_code == 200
    earliest = case.today - timedelta(days=2)
    assert (await case.client.patch(path, json={"plannedDate": earliest.isoformat()})).status_code == 200
    body = await case.days()
    assert body["total"] == 3
    assert body["data"]["deliveryDays"] == [empty_card(case.today - timedelta(days=i)) for i in range(3)]


async def test_aggregates_use_points_saved_prices_and_unique_historical_names(case):
    day = case.today
    # Repeated clients in separate sheets count as separate visits, and empty points count too.
    await case.create(
        day,
        delivery=True,
        points=[
            case.point(name="Вода Родниковая"),
            {"clientId": case.customer_ids[1], "items": []},
        ],
    )
    await case.create(day, delivery=True, points=[case.point(name="Вода Горная", quantity=3)])
    pickup = case.point(name="Вода Горная", quantity=1, price=2.675)
    pickup["items"].extend(
        [
            case.point(product=1, name="Вода Горная", price=0)["items"][0],
            case.point(product=2, name="Бесплатный", quantity=2, price=0)["items"][0],
        ]
    )
    await case.create(day, points=[pickup])
    cancelled = await case.create(day, points=[case.point(name="Отменённое имя", quantity=100, price=999)])
    assert (await case.client.post(f"{case.path(cancelled)}/cancel")).status_code == 200
    await case.create(day)  # Empty active draft is not a visit.
    for product_id in case.product_ids:
        response = await case.client.patch(
            f"/protected/products/{product_id}", json={"isActive": False, "name": unique_product_name("renamed")}
        )
        assert response.status_code == 200
    body = await case.days()
    card = body["data"]["deliveryDays"][0]
    assert body["total"] == 1
    assert card["deliveryPointsCount"] == 3
    assert card["pickupPointsCount"] == 1
    assert card["totalAmount"] == 6.71  # 1.01 + 3.02 + 2.68, rounded before summing.
    products = {product["productId"]: product for product in card["products"]}
    assert products == {
        case.product_ids[0]: {
            "productId": case.product_ids[0],
            "productName": "Вода Горная / Вода Родниковая",
            "quantity": 5,
        },
        case.product_ids[1]: {"productId": case.product_ids[1], "productName": "Вода Горная", "quantity": 1},
        case.product_ids[2]: {"productId": case.product_ids[2], "productName": "Бесплатный", "quantity": 2},
    }
    assert [p["productId"] for p in card["products"]] == sorted(case.product_ids)


async def test_exact_names_are_not_trimmed_or_limited_after_concatenation(case):
    names = ["Ж" * 120, "А" * 120, " А", "А", " А"]
    for name in names:
        await case.create(case.today, points=[case.point(name=name)])
    product = (await case.days())["data"]["deliveryDays"][0]["products"][0]
    assert product["productName"] == " / ".join(sorted(set(names)))
    assert product["quantity"] == 5


async def test_day_documents_are_flat_complete_and_match_document_api(case):
    day = case.today
    delivery = await case.create(
        day,
        delivery=True,
        points=[
            {"clientId": case.customer_ids[1], "items": []},
            case.point(name="Снимок"),
        ],
    )
    pickup = await case.create(day, points=[case.point(name="Другой снимок")])
    cancelled = await case.create(day)
    assert (await case.client.post(f"{case.path(cancelled)}/cancel")).status_code == 200
    await case.create(day + timedelta(days=1))
    # Reading a locked document is allowed.
    assert (await case.client.post(f"{case.path(delivery)}/edit-lock")).status_code == 200
    body = await case.documents(day)
    assert body["total"] == 2
    assert body["offset"] is None
    assert body["limit"] is None
    assert [d["documentType"] for d in body["data"]["documents"]] == ["deliveryRouteSheet", "pickupSheet"]
    for listed in body["data"]["documents"]:
        original = delivery if listed["documentType"] == "deliveryRouteSheet" else pickup
        direct = (await case.client.get(case.path(original))).json()["data"]
        assert listed == {**direct, "documentType": listed["documentType"]}
        assert "document" not in listed
    all_docs = await case.documents(day, include_cancelled=True)
    assert all_docs["total"] == 3
    assert [d["isActive"] for d in all_docs["data"]["documents"]] == [True, True, False]
    assert all_docs["data"]["documents"][-1]["deliveryDocumentId"] == cancelled["deliveryDocumentId"]
    assert (await case.documents(date(1900, 1, 1)))["data"] == {"documents": []}


async def test_document_list_has_no_ten_item_limit_or_pagination(case):
    for _ in range(12):
        await case.create(case.today)
    body = await case.documents(case.today, offset=100, limit=1)
    assert body["total"] == len(body["data"]["documents"]) == 12


async def test_sorting_ties_use_document_id_after_active_status(case, postgres):
    documents = [await case.create(case.today, delivery=bool(i % 2)) for i in range(4)]
    for document in documents[::2]:
        assert (await case.client.post(f"{case.path(document)}/cancel")).status_code == 200
    # Equal creation timestamps cannot be supplied through the document API.
    async with postgres.session_factory() as session:
        await session.execute(
            text("UPDATE delivery_documents SET created_at = :created"), {"created": datetime(2026, 1, 1)}
        )
        await session.commit()
    body = await case.documents(case.today, include_cancelled=True)
    expected = sorted([d["deliveryDocumentId"] for d in documents[1::2]], reverse=True)
    expected += sorted([d["deliveryDocumentId"] for d in documents[::2]], reverse=True)
    assert [d["deliveryDocumentId"] for d in body["data"]["documents"]] == expected


async def test_saved_cancelled_restored_and_moved_documents_refresh_days(case):
    document = await case.create(case.today, points=[case.point(quantity=2, price=10)])
    path = case.path(document)
    assert (await case.days())["data"]["deliveryDays"][0]["totalAmount"] == 20
    assert (await case.client.post(f"{path}/edit-lock")).status_code == 200
    point = document["points"][0]
    payload = {
        "points": [
            {
                "pointId": point["pointId"],
                "clientId": point["clientId"],
                "items": [{**point["items"][0], "quantity": 3, "price": 1.005}],
            }
        ]
    }
    assert (await case.client.patch(path, json=payload)).status_code == 200
    assert (await case.days())["data"]["deliveryDays"][0]["totalAmount"] == 3.02
    assert (await case.client.post(f"{path}/cancel")).status_code == 200
    assert (await case.days())["data"]["deliveryDays"] == [empty_card(case.today)]
    assert (await case.documents(case.today))["total"] == 0
    assert (await case.client.post(f"{path}/restore")).status_code == 200
    assert (await case.documents(case.today))["total"] == 1
    assert (await case.client.post(f"{path}/edit-lock")).status_code == 200
    earlier = case.today - timedelta(days=3)
    assert (await case.client.patch(path, json={"plannedDate": earlier.isoformat()})).status_code == 200
    body = await case.days()
    assert body["total"] == 4
    assert body["data"]["deliveryDays"][:3] == [empty_card(case.today - timedelta(days=i)) for i in range(3)]
    assert body["data"]["deliveryDays"][-1]["totalAmount"] == 3.02
    assert (await case.documents(case.today))["total"] == 0
    assert (await case.documents(earlier))["total"] == 1
    later = case.today + timedelta(days=2)
    assert (await case.client.patch(path, json={"plannedDate": later.isoformat()})).status_code == 200
    body = await case.days()
    assert body["total"] == 1
    assert body["data"]["deliveryDays"][0]["plannedDate"] == later.isoformat()


async def test_document_client_fields_match_direct_api_after_catalog_changes(case):
    response = await case.client.post("/protected/payment-methods/create", json={"name": f"Payment {uuid7()}"})
    assert response.status_code == 201
    payment = response.json()["data"]
    response = await case.client.post(
        "/protected/sales-representatives/create",
        json={
            "name": f"Representative {uuid7()}",
            "phone": unique_phone(),
            "commissionPercent": 10,
        },
    )
    assert response.status_code == 201
    representative = response.json()["data"]
    response = await case.client.patch(
        f"/protected/clients/{case.customer_ids[0]}",
        json={
            "defaultPaymentMethodId": payment["paymentMethodId"],
            "salesRepresentativeId": representative["salesRepresentativeId"],
        },
    )
    assert response.status_code == 200
    document = await case.create(case.today, delivery=True, points=[case.point(name="Историческое имя")])
    for resource, identifier in (
        ("clients", case.customer_ids[0]),
        ("products", case.product_ids[0]),
        ("drivers", case.driver_id),
        ("cars", case.car_id),
        ("payment-methods", payment["paymentMethodId"]),
        ("sales-representatives", representative["salesRepresentativeId"]),
    ):
        assert (
            await case.client.patch(f"/protected/{resource}/{identifier}", json={"isActive": False})
        ).status_code == 200
    assert (
        await case.client.patch(
            f"/protected/clients/{case.customer_ids[0]}", json={"name": "Новое имя клиента", "address": "Новый адрес"}
        )
    ).status_code == 200
    direct = (await case.client.get(case.path(document))).json()["data"]
    listed = (await case.documents(case.today))["data"]["documents"][0]
    assert listed == {**direct, "documentType": "deliveryRouteSheet"}
    point = listed["points"][0]
    assert point["clientName"] == "Новое имя клиента"
    assert point["address"] == "Новый адрес"
    assert point["defaultPaymentMethodId"] == payment["paymentMethodId"]
    assert point["defaultPaymentMethodName"] == payment["name"]
    assert point["salesRepresentativeId"] == representative["salesRepresentativeId"]
    assert point["salesRepresentativeName"] == representative["name"]
    assert point["items"][0]["productName"] == "Историческое имя"


async def test_reading_days_and_documents_preserves_events_and_locks(case, postgres, employee_factory):
    document = await case.create(case.today, points=[case.point()])
    await case.create(case.today, delivery=True)
    assert (await case.client.post(f"{case.path(document)}/edit-lock")).status_code == 200
    other_employee = await employee_factory()
    await DeliveryAPI.login(case.client, other_employee)

    async def read_state():
        async with postgres.session_factory() as session:
            events = (await session.execute(text("SELECT COUNT(*) FROM events"))).scalar_one()
            locks = (
                await session.execute(
                    text(
                        "SELECT delivery_document_id, employee_id, expires_at "
                        "FROM delivery_document_edit_locks ORDER BY delivery_document_id"
                    )
                )
            ).all()
            return events, locks

    before = await read_state()
    assert len(before[1]) == 1
    assert (await case.days())["total"] == 1
    assert (await case.documents(case.today))["total"] == 2
    assert (await case.documents(case.today, include_cancelled=True))["total"] == 2
    assert await read_state() == before


async def test_large_pagination_values_are_bounded_by_calendar_range(case):
    await case.create(case.today - timedelta(days=2))
    body = await case.days(offset=10**30, limit=10**30)
    assert body["total"] == 3
    assert body["data"] == {"deliveryDays": []}
    body = await case.days(offset=1, limit=10**30)
    assert body["data"]["deliveryDays"] == [empty_card(case.today - timedelta(days=i)) for i in (1, 2)]


async def test_rounding_preserves_saved_float_values_near_half_cent(case):
    for price in (1.0049999999999997, 1.0050000000000001, 2.6749999999999994, 2.6750000000000003):
        await case.create(case.today, points=[case.point(price=price)])
    card = (await case.days())["data"]["deliveryDays"][0]
    assert card["totalAmount"] == 7.36  # 1.00 + 1.01 + 2.67 + 2.68.
