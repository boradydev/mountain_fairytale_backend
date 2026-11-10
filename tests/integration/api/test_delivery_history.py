from datetime import date

import pytest
from sqlalchemy import text

from src.feat.delivery_document.domain.delivery_history_models import history_last_date
from tests.document_requests import create_delivery
from tests.helpers import unique_product_name
from tests.integration.api.test_delivery_document_routers import TestDeliveryDocumentRouters as API


@pytest.mark.parametrize(
    ("start", "end"),
    [(date(2024, 2, 29), date(2025, 2, 28)), (date(2023, 3, 1), date(2024, 2, 29))],
)
def test_history_calendar_year(start, end):
    assert history_last_date(start) == end


async def test_history_search_keeps_document_totals(client, active_employee, client_factory):
    await API.login(client, active_employee)
    first = await client_factory(name="History needle", address="North avenue", phone="+7 (999) 123-45-67")
    second = await client_factory(name="History other")
    product = await API.create_product(client, unique_product_name("history"))
    created = await create_delivery(
        client,
        json={
            "plannedDate": "2197-06-12",
            "points": [
                API.point_payload(str(first.client_id), product["productId"], price=12.5),
                API.point_payload(str(second.client_id), product["productId"], price=20),
            ],
        },
    )
    assert created.status_code == 201, created.text
    document_id = created.json()["data"]["deliveryDocumentId"]
    params = {"date_from": "2197-06-12", "date_to": "2197-06-12"}
    for search in ["needle", "North avenue", "9991234567"]:
        response = await client.get("/protected/delivery-history", params={**params, "search": search})
        assert response.status_code == 200, response.text
        assert response.json()["total"] == 1
        doc = response.json()["data"]["documents"][0]
        assert doc["deliveryDocumentId"] == document_id
        assert doc["totalAmount"] == "65.00"
        assert doc["clientsCount"] == 2
        assert len(doc["matchedClients"]) == 1
        assert doc["matchedClients"][0]["totalAmount"] == "25.00"
        assert doc["matchedClients"][0]["items"][0]["productName"] == "Товар"
    response = await client.get("/protected/delivery-history", params=params)
    assert response.json()["data"]["documents"][0]["matchedClients"] == []
    assert (await client.post(f"/protected/delivery-route-sheets/{document_id}/cancel")).status_code == 200
    assert (await client.get("/protected/delivery-history", params=params)).json()["total"] == 0
    params["include_cancelled"] = "true"
    assert (await client.get("/protected/delivery-history", params=params)).json()["total"] == 1


async def test_history_dates_and_anonymous_pickup(client, active_employee):
    await API.login(client, active_employee)
    for params in [
        {},
        {"date_from": "2026-01-01", "date_to": "2027-01-01"},
        {"date_from": "2026-01-02", "date_to": "2026-01-01"},
    ]:
        assert (await client.get("/protected/delivery-history", params=params)).status_code == 422
    for day in ["2196-06-11", "2196-06-12"]:
        response = await client.post(
            "/protected/pickup-sheets/create",
            json={
                "plannedDate": day,
                "points": [{"items": []}, {"items": []}],
            },
        )
        assert response.status_code == 201, response.text
    params = {"date_from": "2196-06-01", "date_to": "2196-06-30", "limit": 1}
    response = await client.get("/protected/delivery-history", params=params)
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 2
    doc = response.json()["data"]["documents"][0]
    assert doc["plannedDate"] == "2196-06-12"
    assert doc["purchasesCount"] == 2
    assert doc["driverName"] is None
    response = await client.get("/protected/delivery-history", params={**params, "offset": 1})
    assert response.json()["data"]["documents"][0]["plannedDate"] == "2196-06-11"
    assert (await client.get("/protected/delivery-history", params={**params, "search": "anonymous"})).json()[
        "total"
    ] == 0


async def test_history_multiple_matches_literal_search_historical_items_and_inactive(
    client,
    active_employee,
    client_factory,
    postgres,
):
    await API.login(client, active_employee)
    first = await client_factory(name=r"History %_\ customer", address="first address")
    second = await client_factory(name=r"History %_\ customer", address="second address")
    third = await client_factory(name="History ordinary customer")
    product = await API.create_product(client, unique_product_name("historical"))
    payment = await client.post("/protected/payment-methods/create", json={"name": "History payment"})
    payment_id = payment.json()["data"]["paymentMethodId"]
    points = [
        API.point_payload(str(c.client_id), product["productId"], price=10.25, product_name="Saved product name")
        for c in [first, second, third]
    ]
    points[0]["paymentMethodId"] = payment_id
    response = await create_delivery(client, json={"plannedDate": "2195-03-10", "points": points})
    assert response.status_code == 201, response.text
    document = response.json()["data"]
    async with postgres.session_factory() as session:
        await session.execute(
            text("UPDATE clients SET is_active = false WHERE client_id = :id"), {"id": first.client_id}
        )
        await session.execute(
            text("UPDATE payment_methods SET is_active = false WHERE payment_method_id = :id"), {"id": payment_id}
        )
        await session.commit()
    params = {"date_from": "2195-03-10", "date_to": "2195-03-10", "search": r"%_\ customer"}
    response = await client.get("/protected/delivery-history", params=params)
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1
    record = response.json()["data"]["documents"][0]
    assert record["totalAmount"] == "61.50"
    assert record["clientsCount"] == 3
    assert {c["clientId"] for c in record["matchedClients"]} == {str(first.client_id), str(second.client_id)}
    purchase = record["matchedClients"][0]
    assert purchase["paymentMethodName"] == "History payment"
    assert purchase["items"][0]["productName"] == "Saved product name"
    assert purchase["items"][0]["price"] == "10.25"
    assert record["driverName"]
    assert record["carModelAndNumber"]
    # The read endpoint neither acquires an edit lock nor changes document revision.
    reloaded = await client.get(f"/protected/delivery-route-sheets/{document['deliveryDocumentId']}")
    assert reloaded.json()["data"] == document
    assert (
        await client.post(f"/protected/delivery-route-sheets/{document['deliveryDocumentId']}/edit-lock")
    ).status_code == 200
    beyond = await client.get("/protected/delivery-history", params={**params, "offset": 100})
    assert beyond.json()["total"] == 1
    assert beyond.json()["data"]["documents"] == []


async def test_history_requires_authorization(client):
    response = await client.get(
        "/protected/delivery-history",
        params={
            "date_from": "2026-01-01",
            "date_to": "2026-01-02",
        },
    )
    assert response.status_code == 401
