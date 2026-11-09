from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import text

from tests.document_requests import create_delivery, patch_with_revision
from tests.helpers import delivery_address, unique_phone, unique_product_name
from tests.integration.api.test_delivery_document_routers import (
    DELIVERY_BASE_PATH,
    TestDeliveryDocumentRouters as DeliveryAPI,
)


async def test_last_order_combines_sales_and_tracks_document_changes(
    client,
    active_employee,
    car_factory,
):
    await DeliveryAPI.login(client, active_employee)
    customers = []
    for index in range(2):
        response = await client.post(
            "/protected/clients/create",
            json={
                "name": f"Last order {index}",
                "phone": unique_phone(),
                "deliveryAddress": delivery_address(),
                "sleepingThresholdDays": 10,
            },
        )
        assert response.status_code == 201
        customers.append(response.json()["data"])
    customer_id = customers[0]["clientId"]
    product = await DeliveryAPI.create_product(client, unique_product_name("last_order"))
    product_id = product["productId"]
    day = date(2026, 10, 10)

    def point(quantity=2, name="Вода 19 л", customer=customer_id):
        return DeliveryAPI.point_payload(customer, product_id, quantity=quantity, product_name=name)

    async def read():
        response = await client.get(f"/protected/clients/{customer_id}")
        assert response.status_code == 200, response.text
        return response.json()["data"]

    async def sale(day, points):
        response = await create_delivery(client, json={"plannedDate": day.isoformat(), "points": points})
        assert response.status_code == 201, response.text
        return response.json()["data"]

    async def patch(path, payload):
        assert (await client.post(f"{path}/edit-lock")).status_code == 200
        response = await patch_with_revision(client, path, json=payload)
        assert response.status_code == 200, response.text
        assert (await client.delete(f"{path}/edit-lock")).status_code == 200
        return response.json()["data"]

    assert (await read())["lastOrder"] is None
    older = await sale(day - timedelta(days=1), [point(quantity=1)])
    driver = await DeliveryAPI.create_driver(client, "Last order driver")
    car = await car_factory()
    response = await client.post(
        f"{DELIVERY_BASE_PATH}/create",
        json={
            "plannedDate": day.isoformat(),
            "driverId": driver["driverId"],
            "carId": str(car.car_id),
            "startMileage": 0,
            "points": [point(quantity=2)],
        },
    )
    assert response.status_code == 201, response.text
    delivery = response.json()["data"]
    latest = await sale(day, [point(quantity=3, name="Вода историческая")])
    latest_path = f"{DELIVERY_BASE_PATH}/{latest['deliveryDocumentId']}"
    expected = {
        "date": day.isoformat(),
        "fulfillmentTypes": ["delivery"],
        "items": [{"productId": product_id, "productName": "Вода историческая", "quantity": 5}],
    }
    current = await read()
    assert current["lastOrder"] == expected
    assert current["lastDeliveryDate"] == "2026-10-10T00:00:00"
    assert current["lastDeliveryQuantity"] == 5
    # A late-entered older sale and empty newer points must not replace the latest sale.
    await sale(day - timedelta(days=5), [point(quantity=99)])
    await sale(day + timedelta(days=1), [{"clientId": customer_id, "items": []}])
    assert (await read())["lastOrder"] == expected
    # Editing quantities must update both the composition and the compatibility total.
    changed_point = point(quantity=7)
    changed_point["pointId"] = latest["points"][0]["pointId"]
    await patch(latest_path, {"points": [changed_point]})
    expected["items"][0]["quantity"] = 9
    assert (await read())["lastOrder"] == expected
    assert (await read())["lastDeliveryQuantity"] == 9
    # Renaming/deactivating a product never rewrites historical order names.
    response = await patch_with_revision(
        client, f"/protected/products/{product_id}", json={"name": unique_product_name("renamed"), "isActive": False}
    )
    assert response.status_code == 200, response.text
    assert (await read())["lastOrder"] == expected
    response = await client.get("/protected/clients", params={"search": customers[0]["phone"]})
    assert response.status_code == 200
    assert response.json()["data"]["clients"][0]["lastOrder"] == expected
    response = await client.get(
        "/protected/clients/check-duplicate", params={key: customers[0][key] for key in ("name", "phone", "address")}
    )
    assert response.status_code == 200
    assert response.json()["data"]["lastOrder"] == expected
    response = await patch_with_revision(
        client, f"/protected/clients/{customer_id}", json={"deliveryAddress": delivery_address(house="148")}
    )
    assert response.status_code == 200
    assert response.json()["data"]["lastOrder"] == expected

    assert (await client.post(f"{latest_path}/cancel")).status_code == 200
    assert (await read())["lastOrder"]["fulfillmentTypes"] == ["delivery"]
    assert (await read())["lastDeliveryQuantity"] == 2
    assert (await client.post(f"{latest_path}/restore")).status_code == 200
    assert (await read())["lastOrder"] == expected
    # Move the latest delivery to another day and then remove all its goods.
    await patch(latest_path, {"plannedDate": (day + timedelta(days=2)).isoformat()})
    assert (await read())["lastOrder"]["fulfillmentTypes"] == ["delivery"]
    assert (await read())["lastDeliveryQuantity"] == 7
    await patch(
        latest_path, {"points": [{"pointId": latest["points"][0]["pointId"], "clientId": customer_id, "items": []}]}
    )
    assert (await read())["lastDeliveryQuantity"] == 2
    # Removing a client point must remove it from the original client's summary.
    assert (
        await patch_with_revision(client, f"/protected/products/{product_id}", json={"isActive": True})
    ).status_code == 200
    delivery_path = f"{DELIVERY_BASE_PATH}/{delivery['deliveryDocumentId']}"
    await patch(delivery_path, {"points": [point(quantity=4, customer=customers[1]["clientId"])]})
    assert (await read())["lastOrder"]["date"] == (day - timedelta(days=1)).isoformat()
    other = await client.get(f"/protected/clients/{customers[1]['clientId']}")
    assert other.json()["data"]["lastDeliveryQuantity"] == 4
    assert (await client.post(f"{DELIVERY_BASE_PATH}/{older['deliveryDocumentId']}/cancel")).status_code == 200
    assert (await read())["lastOrder"]["date"] == (day - timedelta(days=5)).isoformat()


async def test_cancelling_only_sale_returns_null_summary(client, active_employee, client_factory):
    await DeliveryAPI.login(client, active_employee)
    customer = await client_factory(phone=unique_phone())
    product = await DeliveryAPI.create_product(client, unique_product_name("only_sale"))
    response = await create_delivery(
        client,
        json={
            "plannedDate": "2026-10-10",
            "points": [DeliveryAPI.point_payload(str(customer.client_id), product["productId"])],
        },
    )
    assert response.status_code == 201
    document_id = response.json()["data"]["deliveryDocumentId"]
    assert (await client.post(f"{DELIVERY_BASE_PATH}/{document_id}/cancel")).status_code == 200
    response = await client.get(f"/protected/clients/{customer.client_id}")
    assert response.status_code == 200
    for field in ("lastOrder", "lastDeliveryDate", "lastDeliveryQuantity"):
        assert response.json()["data"][field] is None


async def test_list_keeps_clients_and_distinct_products_separate(client, active_employee, client_factory):
    await DeliveryAPI.login(client, active_employee)
    customers = [await client_factory(phone=unique_phone()) for _ in range(2)]
    products = [await DeliveryAPI.create_product(client, unique_product_name("composition")) for _ in range(2)]
    points = []
    for index, customer in enumerate(customers):
        points.append(
            {
                "clientId": str(customer.client_id),
                "items": [
                    {
                        "productId": product["productId"],
                        "productName": "Историческое имя",
                        "quantity": index + number + 1,
                        "price": 0,
                    }
                    for number, product in enumerate(products)
                ],
            }
        )
    response = await create_delivery(client, json={"plannedDate": "2026-10-12", "points": points})
    assert response.status_code == 201, response.text
    response = await client.get("/protected/clients", params={"limit": 1000})
    assert response.status_code == 200
    rows = {row["clientId"]: row for row in response.json()["data"]["clients"]}
    for index, customer in enumerate(customers):
        row = rows[str(customer.client_id)]
        assert row["lastDeliveryQuantity"] == 3 + 2 * index
        items = row["lastOrder"]["items"]
        assert len(items) == 2
        assert {item["productId"]: item["quantity"] for item in items} == {
            product["productId"]: index + number + 1 for number, product in enumerate(products)
        }


@pytest.mark.parametrize("planned", ["2026-10-15", "2026-10-10"])
async def test_latest_order_is_one_point_by_creation_and_keeps_business_date(
    client,
    active_employee,
    client_factory,
    planned,
):
    await DeliveryAPI.login(client, active_employee)
    customer = await client_factory(phone=unique_phone(), sleeping_threshold_days=0)
    customer_id = str(customer.client_id)
    product = await DeliveryAPI.create_product(client, unique_product_name("latest"))
    free = await client.post(
        "/protected/products/create",
        json={
            "name": unique_product_name("service"),
            "basePrice": 999,
            "isFreePrice": True,
        },
    )
    assert free.status_code == 201
    free_id = free.json()["data"]["productId"]
    older = await create_delivery(
        client,
        json={
            "plannedDate": planned,
            "points": [
                DeliveryAPI.point_payload(customer_id, product["productId"], quantity=99),
            ],
        },
    )
    assert older.status_code == 201, older.text
    payload = DeliveryAPI.point_payload(
        customer_id, product["productId"], price=12.345, quantity=3, product_name="Историческая вода"
    )
    payload["items"].extend(
        [
            {
                "productId": free_id,
                "productName": "Историческая услуга",
                "quantity": 1,
                "price": 0.005,
                "isFreePrice": True,
                "driverNote": "Полное сохранённое примечание",
            },
            {
                "productId": free_id,
                "productName": "Та же услуга другой строкой",
                "quantity": 2,
                "price": 2.222,
                "isFreePrice": True,
                "driverNote": "Вторая строка",
            },
        ]
    )
    response = await create_delivery(client, json={"plannedDate": "2026-10-10", "points": [payload]})
    assert response.status_code == 201, response.text
    saved = response.json()["data"]
    path = f"/protected/clients/{customer_id}/latest-order"
    response = await client.get(path)
    assert response.status_code == 200, response.text
    order = response.json()["data"]
    assert order["deliveryDocumentId"] == saved["deliveryDocumentId"]
    assert order["pointId"] == saved["points"][0]["pointId"]
    assert order["createdAt"] == saved["createdAt"]
    assert order["plannedDate"] == "2026-10-10"
    assert len(order["items"]) == 3
    rows = {i["productName"]: i for i in order["items"]}
    assert Decimal(rows["Историческая вода"]["price"]) == Decimal("12.345")
    assert Decimal(rows["Историческая вода"]["amount"]) == Decimal("37.04")
    assert rows["Историческая услуга"]["driverNote"] == "Полное сохранённое примечание"
    assert rows["Историческая услуга"]["isFreePrice"] is True
    assert Decimal(order["totalAmount"]) == Decimal("41.49")
    assert Decimal(order["totalAmount"]) == sum(Decimal(i["amount"]) for i in order["items"])
    # Catalog edits must never affect saved snapshots.
    renamed = await client.patch(
        f"/protected/products/{product['productId']}",
        json={
            "name": unique_product_name("renamed_latest"),
            "basePrice": 500,
            "isActive": False,
        },
    )
    assert renamed.status_code == 200, renamed.text
    assert (await client.get(path)).json()["data"] == order
    current = (await client.get(f"/protected/clients/{customer_id}")).json()["data"]
    assert current["lastDeliveryDate"] == f"{planned}T00:00:00"
    assert current["lastDeliveryQuantity"] == (105 if planned == "2026-10-10" else 99)
    assert current["latestOrderCreatedAt"] == order["createdAt"]
    assert current["latestOrderPlannedDate"] == order["plannedDate"]
    # Both dashboard modes retain pagination and return dates for the same selected order.
    for mode in ("database", "follow_up"):
        page = await client.get(
            "/protected/clients",
            params={
                "search": customer.phone,
                "mode": mode,
                "offset": 0,
                "limit": 1,
            },
        )
        assert page.status_code == 200, page.text
        body = page.json()
        assert body["total"] == 1
        assert body["offset"] == 0
        assert body["limit"] == 1
        row = body["data"]["clients"][0]
        assert row["latestOrderCreatedAt"] == order["createdAt"]
        assert row["latestOrderPlannedDate"] == order["plannedDate"]
        assert row["lastOrder"] == current["lastOrder"]
        assert "latestOrder" not in row
        next_page = await client.get(
            "/protected/clients",
            params={
                "search": customer.phone,
                "mode": mode,
                "offset": 1,
                "limit": 1,
            },
        )
        assert next_page.json()["data"]["clients"] == []
        assert next_page.json()["total"] == 1


@pytest.mark.parametrize("excluded", ["cancelled", "undelivered", "empty"])
async def test_latest_order_skips_ineligible_newer_point(client, active_employee, client_factory, excluded):
    await DeliveryAPI.login(client, active_employee)
    customer = await client_factory(phone=unique_phone())
    customer_id = str(customer.client_id)
    product = await DeliveryAPI.create_product(client, unique_product_name("eligibility"))
    point = DeliveryAPI.point_payload(customer_id, product["productId"])
    response = await create_delivery(client, json={"plannedDate": "2026-10-10", "points": [point]})
    assert response.status_code == 201, response.text
    original = response.json()["data"]
    if excluded == "empty":
        point = {"clientId": customer_id, "items": []}
    elif excluded == "undelivered":
        point = {**point, "isDelivered": False, "nonDeliveryReason": "Клиент отсутствует"}
    response = await create_delivery(client, json={"plannedDate": "2026-10-12", "points": [point]})
    assert response.status_code == 201, response.text
    newer = response.json()["data"]
    if excluded == "cancelled":
        assert (await client.post(f"{DELIVERY_BASE_PATH}/{newer['deliveryDocumentId']}/cancel")).status_code == 200
    response = await client.get(f"/protected/clients/{customer_id}/latest-order")
    assert response.status_code == 200, response.text
    assert response.json()["data"]["deliveryDocumentId"] == original["deliveryDocumentId"]
    summary = (await client.get(f"/protected/clients/{customer_id}")).json()["data"]
    assert summary["latestOrderCreatedAt"] == original["createdAt"]
    assert summary["latestOrderPlannedDate"] == original["plannedDate"]
    assert (await client.post(f"{DELIVERY_BASE_PATH}/{original['deliveryDocumentId']}/cancel")).status_code == 200
    assert (await client.get(f"/protected/clients/{customer_id}/latest-order")).json()["data"] is None
    summary = (await client.get(f"/protected/clients/{customer_id}")).json()["data"]
    assert summary["latestOrderCreatedAt"] is None
    assert summary["latestOrderPlannedDate"] is None
    page = await client.get("/protected/clients", params={"search": customer.phone})
    row = page.json()["data"]["clients"][0]
    assert row["latestOrderCreatedAt"] is None
    assert row["latestOrderPlannedDate"] is None


async def test_latest_order_null_missing_client_and_auth(client, active_employee, client_factory):
    customer = await client_factory(phone=unique_phone())
    path = f"/protected/clients/{customer.client_id}/latest-order"
    assert (await client.get(path)).status_code == 401
    await DeliveryAPI.login(client, active_employee)
    response = await client.get(path)
    assert response.status_code == 200
    assert response.json()["data"] is None
    summary = (await client.get(f"/protected/clients/{customer.client_id}")).json()["data"]
    assert summary["latestOrderCreatedAt"] is None
    assert summary["latestOrderPlannedDate"] is None
    assert (await client.get(f"/protected/clients/{uuid4()}/latest-order")).status_code == 404
    assert (await client.get("/protected/clients/not-a-uuid/latest-order")).status_code == 422


async def test_latest_order_dates_use_same_document_when_creation_times_tie(
    client, active_employee, client_factory, postgres
):
    await DeliveryAPI.login(client, active_employee)
    customer = await client_factory(phone=unique_phone())
    customer_id = str(customer.client_id)
    product = await DeliveryAPI.create_product(client, unique_product_name("latest_tie"))
    documents = []
    for planned in ("2026-11-12", "2026-11-10"):
        response = await create_delivery(
            client,
            json={
                "plannedDate": planned,
                "points": [DeliveryAPI.point_payload(customer_id, product["productId"])],
            },
        )
        assert response.status_code == 201, response.text
        documents.append(response.json()["data"])
    created_at = datetime(2026, 11, 9, 12)
    async with postgres.session_factory() as session:
        for document in documents:
            await session.execute(
                text("UPDATE delivery_documents SET created_at = :created_at WHERE delivery_document_id = :id"),
                {"created_at": created_at, "id": document["deliveryDocumentId"]},
            )
        await session.commit()
    expected = max(documents, key=lambda document: document["deliveryDocumentId"])
    order = (await client.get(f"/protected/clients/{customer_id}/latest-order")).json()["data"]
    assert order["deliveryDocumentId"] == expected["deliveryDocumentId"]
    assert order["pointId"] == expected["points"][0]["pointId"]
    assert order["createdAt"] == created_at.isoformat()
    assert order["plannedDate"] == expected["plannedDate"]
    summary = (await client.get(f"/protected/clients/{customer_id}")).json()["data"]
    page = await client.get("/protected/clients", params={"search": customer.phone})
    for row in (summary, page.json()["data"]["clients"][0]):
        assert row["latestOrderCreatedAt"] == order["createdAt"]
        assert row["latestOrderPlannedDate"] == order["plannedDate"]
