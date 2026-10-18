from datetime import date, timedelta

from tests.helpers import unique_phone, unique_product_name
from tests.integration.api.test_delivery_document_routers import (
    DELIVERY_BASE_PATH,
    PICKUP_BASE_PATH,
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
                "address": "Адрес",
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

    async def pickup(day, points):
        response = await client.post(
            f"{PICKUP_BASE_PATH}/create", json={"plannedDate": day.isoformat(), "points": points}
        )
        assert response.status_code == 201, response.text
        return response.json()["data"]

    async def patch(path, payload):
        assert (await client.post(f"{path}/edit-lock")).status_code == 200
        response = await client.patch(path, json=payload)
        assert response.status_code == 200, response.text
        assert (await client.delete(f"{path}/edit-lock")).status_code == 200
        return response.json()["data"]

    assert (await read())["lastOrder"] is None
    older = await pickup(day - timedelta(days=1), [point(quantity=1)])
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
    latest = await pickup(day, [point(quantity=3, name="Вода историческая")])
    latest_path = f"{PICKUP_BASE_PATH}/{latest['deliveryDocumentId']}"
    expected = {
        "date": day.isoformat(),
        "fulfillmentTypes": ["delivery", "pickup"],
        "items": [{"productId": product_id, "productName": "Вода историческая", "quantity": 5}],
    }
    current = await read()
    assert current["lastOrder"] == expected
    assert current["lastDeliveryDate"] == "2026-10-10T00:00:00"
    assert current["lastDeliveryQuantity"] == 5
    # A late-entered older sale and empty newer points must not replace the latest sale.
    await pickup(day - timedelta(days=5), [point(quantity=99)])
    await pickup(day + timedelta(days=1), [{"clientId": customer_id, "items": []}])
    assert (await read())["lastOrder"] == expected
    # Editing quantities must update both the composition and the compatibility total.
    changed_point = point(quantity=7)
    changed_point["pointId"] = latest["points"][0]["pointId"]
    await patch(latest_path, {"points": [changed_point]})
    expected["items"][0]["quantity"] = 9
    assert (await read())["lastOrder"] == expected
    assert (await read())["lastDeliveryQuantity"] == 9
    # Renaming/deactivating a product never rewrites historical order names.
    response = await client.patch(
        f"/protected/products/{product_id}", json={"name": unique_product_name("renamed"), "isActive": False}
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
    response = await client.patch(f"/protected/clients/{customer_id}", json={"address": "Новый адрес"})
    assert response.status_code == 200
    assert response.json()["data"]["lastOrder"] == expected

    assert (await client.post(f"{latest_path}/cancel")).status_code == 200
    assert (await read())["lastOrder"]["fulfillmentTypes"] == ["delivery"]
    assert (await read())["lastDeliveryQuantity"] == 2
    assert (await client.post(f"{latest_path}/restore")).status_code == 200
    assert (await read())["lastOrder"] == expected
    # Move the latest pickup to another day and then remove all its goods.
    await patch(latest_path, {"plannedDate": (day + timedelta(days=2)).isoformat()})
    assert (await read())["lastOrder"]["fulfillmentTypes"] == ["pickup"]
    assert (await read())["lastDeliveryQuantity"] == 7
    await patch(
        latest_path, {"points": [{"pointId": latest["points"][0]["pointId"], "clientId": customer_id, "items": []}]}
    )
    assert (await read())["lastDeliveryQuantity"] == 2
    # Removing a client point must remove it from the original client's summary.
    assert (await client.patch(f"/protected/products/{product_id}", json={"isActive": True})).status_code == 200
    delivery_path = f"{DELIVERY_BASE_PATH}/{delivery['deliveryDocumentId']}"
    await patch(delivery_path, {"points": [point(quantity=4, customer=customers[1]["clientId"])]})
    assert (await read())["lastOrder"]["date"] == (day - timedelta(days=1)).isoformat()
    other = await client.get(f"/protected/clients/{customers[1]['clientId']}")
    assert other.json()["data"]["lastDeliveryQuantity"] == 4
    assert (await client.post(f"{PICKUP_BASE_PATH}/{older['deliveryDocumentId']}/cancel")).status_code == 200
    assert (await read())["lastOrder"]["date"] == (day - timedelta(days=5)).isoformat()


async def test_cancelling_only_sale_returns_null_summary(client, active_employee, client_factory):
    await DeliveryAPI.login(client, active_employee)
    customer = await client_factory(phone=unique_phone())
    product = await DeliveryAPI.create_product(client, unique_product_name("only_sale"))
    response = await client.post(
        f"{PICKUP_BASE_PATH}/create",
        json={
            "plannedDate": "2026-10-10",
            "points": [DeliveryAPI.point_payload(str(customer.client_id), product["productId"])],
        },
    )
    assert response.status_code == 201
    document_id = response.json()["data"]["deliveryDocumentId"]
    assert (await client.post(f"{PICKUP_BASE_PATH}/{document_id}/cancel")).status_code == 200
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
    response = await client.post(f"{PICKUP_BASE_PATH}/create", json={"plannedDate": "2026-10-12", "points": points})
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
