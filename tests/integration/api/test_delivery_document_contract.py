import asyncio
from datetime import datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from src.common.infra.services.event_pud_service import EventPublisher
from src.core.uuid7 import uuid7
from tests.helpers import unique_car_number, unique_phone, unique_product_name
from tests.integration.api.test_delivery_document_routers import (
    DELIVERY_BASE_PATH,
    PICKUP_BASE_PATH,
    TestDeliveryDocumentRouters as DeliveryAPI,
)


@pytest.fixture(params=[DELIVERY_BASE_PATH, PICKUP_BASE_PATH])
async def document_case(request, client, active_employee) -> dict[str, Any]:
    """Create document and catalog entries through public HTTP endpoints."""
    api = DeliveryAPI()
    await api.login(client, active_employee)
    customers = []
    for _ in range(2):
        response = await client.post(
            "/protected/clients/create",
            json={
                "name": f"Contract client {uuid7()}",
                "phone": unique_phone(),
                "address": "Contract address",
                "sleepingThresholdDays": 10,
            },
        )
        assert response.status_code == 201
        customers.append(response.json()["data"])
    product = await api.create_product(client, unique_product_name("contract"), base_price=99.0)
    points = [
        api.point_payload(customers[0]["clientId"], product["productId"], price=12.5),
        {"clientId": customers[1]["clientId"], "items": []},
    ]
    payload: dict[str, Any] = {"plannedDate": "2025-03-15", "points": points}
    if request.param == DELIVERY_BASE_PATH:
        driver = await api.create_driver(client, f"Contract driver {uuid7()}")
        response = await client.post(
            "/protected/cars/create",
            json={
                "model": "Contract car",
                "number": unique_car_number(),
            },
        )
        assert response.status_code == 201
        payload.update(driverId=driver["driverId"], carId=response.json()["data"]["carId"], startMileage=100.0)
    response = await client.post(f"{request.param}/create", json=payload)
    assert response.status_code == 201
    document = response.json()["data"]
    path = f"{request.param}/{document['deliveryDocumentId']}"
    assert (await client.post(f"{path}/edit-lock")).status_code == 200
    return {
        "base": request.param,
        "path": path,
        "document": document,
        "payload": payload,
        "customers": customers,
        "product": product,
    }


def patch_points(document: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "pointId": point["pointId"],
            "clientId": point["clientId"],
            "items": [{key: item[key] for key in ("productId", "quantity", "price")} for item in point["items"]],
        }
        for point in document["points"]
    ]


async def read_events(postgres, document: dict[str, Any]) -> list[dict[str, Any]]:
    async with postgres.session_factory() as session:
        result = await session.execute(
            text(
                "SELECT event_type, actor_id, payload FROM events "
                "WHERE payload->>'delivery_document_id' = :document_id "
                "OR payload->>'point_id' = ANY(CAST(:point_ids AS text[])) "
                "ORDER BY created_at, event_id",
            ),
            {
                "document_id": document["deliveryDocumentId"],
                "point_ids": [point["pointId"] for point in document["points"]],
            },
        )
        return [dict(row) for row in result.mappings()]


async def test_empty_documents_and_collections(client: AsyncClient, document_case) -> None:
    case = document_case
    payload = {**case["payload"], "points": []}
    response = await client.post(f"{case['base']}/create", json=payload)
    assert response.status_code == 201
    blank = response.json()["data"]
    assert blank["isActive"] is True
    assert blank["points"] == []
    listing = await client.get(case["base"])
    key = "deliveryRouteSheets" if case["base"] == DELIVERY_BASE_PATH else "pickupSheets"
    assert blank["deliveryDocumentId"] in [item["deliveryDocumentId"] for item in listing.json()["data"][key]]
    points = patch_points(case["document"])
    points[0]["items"] = []
    response = await client.patch(case["path"], json={"points": points})
    assert response.status_code == 200
    loaded = (await client.get(case["path"])).json()["data"]
    assert len(loaded["points"]) == 2
    assert all(point["items"] == [] for point in loaded["points"])
    response = await client.patch(case["path"], json={"points": []})
    assert response.status_code == 200
    assert (await client.get(case["path"])).json()["data"]["points"] == []
    response = await client.patch(case["path"], json={"points": points})
    assert response.status_code == 422  # Deleted point IDs cannot be reused.


async def test_existing_inactive_references_and_new_rows(client: AsyncClient, document_case) -> None:
    case = document_case
    customer_id = case["customers"][0]["clientId"]
    product_id = case["product"]["productId"]
    for resource, resource_id in (("clients", customer_id), ("products", product_id)):
        assert (await client.patch(f"/protected/{resource}/{resource_id}", json={"isActive": False})).status_code == 200
    points = patch_points(case["document"])
    points[0]["items"][0].update(quantity=7, price=0.0)
    response = await client.patch(case["path"], json={"points": points})
    assert response.status_code == 200
    saved = response.json()["data"]
    assert saved["points"][0]["items"][0]["quantity"] == 7
    assert saved["points"][0]["items"][0]["price"] == 0.0
    # Inactivity is checked for a new item in each point, not globally per document.
    bad_points = patch_points(saved)
    bad_points[1]["items"] = [{"productId": product_id, "quantity": 1, "price": 99.0}]
    response = await client.patch(case["path"], json={"plannedDate": "2025-04-01", "points": bad_points})
    assert response.status_code == 422
    assert (await client.get(case["path"])).json()["data"] == saved
    # Replacing an existing point for an inactive customer constitutes a new link.
    bad_points = patch_points(saved)
    bad_points[0].pop("pointId")
    bad_points[0]["items"] = []
    assert (await client.patch(case["path"], json={"points": bad_points})).status_code == 422
    assert (await client.get(case["path"])).json()["data"] == saved
    for point in (
        {"clientId": customer_id, "items": []},
        DeliveryAPI.point_payload(case["customers"][1]["clientId"], product_id),
    ):
        response = await client.post(f"{case['base']}/create", json={**case["payload"], "points": [point]})
        assert response.status_code == 422
    assert (await client.patch(f"/protected/products/{product_id}", json={"isActive": True})).status_code == 200
    points = patch_points(saved)
    points[1]["items"] = [{"productId": product_id, "quantity": 1, "price": 99.0}]
    assert (await client.patch(case["path"], json={"points": points})).status_code == 200


async def test_client_identity_and_point_replacement_are_atomic(client: AsyncClient, document_case, postgres) -> None:
    case = document_case
    saved = case["document"]
    events = await read_events(postgres, saved)
    points = patch_points(saved)
    points[0]["clientId"] = case["customers"][1]["clientId"]
    points = points[:1]
    response = await client.patch(case["path"], json={"plannedDate": "2025-04-01", "points": points})
    assert response.status_code == 422
    assert (await client.get(case["path"])).json()["data"] == saved
    assert await read_events(postgres, saved) == events
    points = patch_points(saved)
    # Re-create a point for the same client while reversing order.
    points[0].pop("pointId")
    response = await client.patch(case["path"], json={"points": list(reversed(points))})
    assert response.status_code == 200
    loaded = (await client.get(case["path"])).json()["data"]
    assert [point["clientId"] for point in loaded["points"]] == [p["clientId"] for p in reversed(saved["points"])]
    assert [point["position"] for point in loaded["points"]] == [0, 1]
    assert loaded["points"][1]["pointId"] != saved["points"][0]["pointId"]
    assert loaded["points"][1]["items"] == saved["points"][0]["items"]
    events = await read_events(postgres, saved)
    deleted = next(event for event in events if event["event_type"] == "DeletePointEvent")
    assert deleted["payload"]["data"]["client_id"] == saved["points"][0]["clientId"]
    assert deleted["payload"]["data"]["items"][0]["price"] == 12.5
    assert any(event["event_type"] == "DeleteItemEvent" for event in events)


async def test_cancel_removes_own_lock_and_restore_preserves_data(
    client: AsyncClient, document_case, active_employee, postgres
) -> None:
    case = document_case
    response = await client.post(f"{case['path']}/cancel")
    assert response.status_code == 200
    cancelled = response.json()["data"]
    assert cancelled == {**case["document"], "isActive": False}
    for method in (client.post, client.patch):
        response = await method(f"{case['path']}/edit-lock")
        assert response.status_code == 409
        assert response.json() == {"detail": "Delivery document is cancelled"}
    assert (await client.delete(f"{case['path']}/edit-lock")).status_code == 409
    assert (await client.patch(case["path"], json={"points": []})).status_code == 422
    assert (await client.post(f"{case['path']}/restore")).json()["data"] == case["document"]
    assert (await client.patch(case["path"], json={"points": []})).status_code == 409
    response = await client.post(f"{case['path']}/edit-lock")
    assert response.status_code == 200
    assert response.json()["data"]["ownerName"] == active_employee.username
    events = await read_events(postgres, case["document"])
    for event_type, previous, current in (
        ("CancelDeliveryDocumentEvent", True, False),
        ("RestoreDeliveryDocumentEvent", False, True),
    ):
        event = next(event for event in events if event["event_type"] == event_type)
        assert event["payload"]["changes"]["is_active"] == {"old": previous, "new": current}


async def test_foreign_lock_conflicts_include_owner(
    client: AsyncClient, document_case, employee_factory, active_employee
) -> None:
    case = document_case
    other = await employee_factory()
    await DeliveryAPI.login(client, other)
    for suffix in ("/edit-lock", "/cancel", "/restore"):
        response = await client.post(f"{case['path']}{suffix}")
        assert response.status_code == 423
        assert response.json() == {
            "detail": "Delivery document is locked by another employee",
            "ownerName": active_employee.username,
        }
    response = await client.patch(case["path"], json={"points": []})
    assert response.status_code == 423
    assert response.json()["ownerName"] == active_employee.username
    assert (await client.get(case["path"])).json()["data"] == case["document"]
    assert (await client.patch(f"{case['path']}/edit-lock")).status_code == 403
    assert (await client.delete(f"{case['path']}/edit-lock")).status_code == 403


async def test_expired_lock_can_be_taken_over(client: AsyncClient, document_case, postgres, employee_factory) -> None:
    case = document_case
    # The API cannot move server time; prepare expiration directly without sleeping.
    async with postgres.session_factory() as session:
        await session.execute(
            text(
                "UPDATE delivery_document_edit_locks SET expires_at = :expires_at WHERE delivery_document_id = :id",
            ),
            {"expires_at": datetime.now() - timedelta(seconds=1), "id": case["document"]["deliveryDocumentId"]},
        )
        await session.commit()
    assert (await client.patch(f"{case['path']}/edit-lock")).status_code == 409
    assert (await client.delete(f"{case['path']}/edit-lock")).status_code == 409
    assert (await client.patch(case["path"], json={"points": []})).status_code == 409
    other = await employee_factory()
    await DeliveryAPI.login(client, other)
    response = await client.post(f"{case['path']}/edit-lock")
    assert response.status_code == 200
    assert response.json()["data"]["ownerName"] == other.username
    assert (await client.patch(case["path"], json={"points": []})).status_code == 200


async def test_history_records_root_and_children(client: AsyncClient, document_case, postgres, active_employee) -> None:
    case = document_case
    events = await read_events(postgres, case["document"])
    assert all(str(event["actor_id"]) == str(active_employee.employee_id) for event in events)
    created = next(event["payload"] for event in events if event["event_type"] == "CreateDeliveryDocumentEvent")
    assert created["data"]["planned_date"] == "2025-03-15"
    assert created["data"]["points"][0]["items"][0]["price"] == 12.5
    points = patch_points(case["document"])
    points[0]["items"][0].update(quantity=3, price=15.0)
    assert (await client.patch(case["path"], json={"points": points})).status_code == 200
    events = await read_events(postgres, case["document"])
    item = next(event["payload"] for event in events if event["event_type"] == "UpdateItemEvent")
    assert item["changes"]["quantity"] == {"old": 2, "new": 3}
    assert item["changes"]["price"] == {"old": 12.5, "new": 15.0}
    assert any(event["event_type"] == "UpdatePointEvent" for event in events)
    root = next(event["payload"] for event in events if event["event_type"] == "UpdateDeliveryDocumentEvent")
    assert root["changes"]["points"]["old"][0]["items"][0]["quantity"] == 2
    assert root["changes"]["points"]["new"][0]["items"][0]["quantity"] == 3
    count = len(events)
    assert (await client.patch(case["path"], json={"points": points})).status_code == 200
    assert len(await read_events(postgres, case["document"])) == count


@pytest.mark.parametrize("resource", ["drivers", "cars"])
@pytest.mark.parametrize("document_case", [DELIVERY_BASE_PATH], indirect=True)
async def test_inactive_assignment_can_be_retained_but_not_changed(
    client: AsyncClient, document_case, resource
) -> None:
    case = document_case
    document = case["document"]
    resource_id = document["driverId" if resource == "drivers" else "carId"]
    assert (await client.patch(f"/protected/{resource}/{resource_id}", json={"isActive": False})).status_code == 200
    response = await client.patch(
        case["path"],
        json={
            "driverId": document["driverId"],
            "carId": document["carId"],
            "plannedDate": document["plannedDate"],
            "endMileage": 200.0,
        },
    )
    assert response.status_code == 200
    saved = response.json()["data"]
    # Changing the date must validate both resources, not just an explicitly sent ID.
    response = await client.patch(case["path"], json={"plannedDate": "2025-04-01"})
    assert response.status_code == 422
    assert (await client.get(case["path"])).json()["data"] == saved
    # Changing the other resource still requires the inactive resource to be active.
    if resource == "cars":
        alternative = await DeliveryAPI.create_driver(client, f"Alternative driver {uuid7()}")
        changed_assignment = {"driverId": alternative["driverId"]}
    else:
        response = await client.post(
            "/protected/cars/create",
            json={
                "model": "Alternative car",
                "number": unique_car_number(),
            },
        )
        assert response.status_code == 201
        changed_assignment = {"carId": response.json()["data"]["carId"]}
    assert (await client.patch(case["path"], json=changed_assignment)).status_code == 422
    assert (await client.get(case["path"])).json()["data"] == saved
    response = await client.post(f"{case['base']}/create", json=case["payload"])
    assert response.status_code == 422
    assert (await client.patch(f"/protected/{resource}/{resource_id}", json={"isActive": True})).status_code == 200
    assert (await client.patch(case["path"], json={"plannedDate": "2025-04-01"})).status_code == 200


@pytest.mark.parametrize("document_case", [DELIVERY_BASE_PATH], indirect=True)
async def test_mileage_validates_combined_state_and_explicit_null(client: AsyncClient, document_case) -> None:
    path = document_case["path"]
    assert (await client.patch(path, json={"endMileage": 200.0})).status_code == 200
    saved = (await client.get(path)).json()["data"]
    assert (await client.patch(path, json={"startMileage": 200.0})).status_code == 422
    assert (await client.get(path)).json()["data"] == saved
    assert (await client.patch(path, json={"endMileage": None})).status_code == 200
    assert (await client.get(path)).json()["data"]["endMileage"] is None
    for field in ("plannedDate", "driverId", "carId", "startMileage", "points"):
        assert (await client.patch(path, json={field: None})).status_code == 422
    assert (await client.patch(path, json={"startMileage": -1})).status_code == 422


async def test_concurrent_lock_acquisition_has_one_owner(
    client: AsyncClient, document_case, employee_factory, active_employee
) -> None:
    case = document_case
    lock_path = f"{case['path']}/edit-lock"
    assert (await client.delete(lock_path)).status_code == 200
    owner_token = client.cookies.get("access-token")
    assert owner_token
    other = await employee_factory()
    await DeliveryAPI.login(client, other)
    other_token = client.cookies.get("access-token")
    assert other_token
    responses = await asyncio.gather(
        client.post(lock_path, headers={"Authorization": f"Bearer {owner_token}"}),
        client.post(lock_path, headers={"Authorization": f"Bearer {other_token}"}),
    )
    assert sorted(response.status_code for response in responses) == [200, 423]
    winner = next(index for index, response in enumerate(responses) if response.status_code == 200)
    owner = (active_employee.username, other.username)[winner]
    assert responses[winner].json()["data"]["ownerName"] == owner
    assert responses[1 - winner].json()["ownerName"] == owner


@pytest.mark.parametrize("operation", ["update", "cancel"])
async def test_event_failure_rolls_back_document_and_lock(
    client: AsyncClient, document_case, postgres, monkeypatch, operation
) -> None:
    case = document_case
    previous_events = await read_events(postgres, case["document"])

    async def fail_publish(self, *, events) -> None:
        raise RuntimeError("Simulated event persistence failure")

    with monkeypatch.context() as patch:
        patch.setattr(EventPublisher, "publish_many", fail_publish)
        request = (
            client.post(f"{case['path']}/cancel")
            if operation == "cancel"
            else client.patch(case["path"], json={"plannedDate": "2025-04-01", "points": []})
        )
        with pytest.raises(RuntimeError, match="Simulated event persistence failure"):
            await request
    assert (await client.get(case["path"])).json()["data"] == case["document"]
    assert await read_events(postgres, case["document"]) == previous_events
    assert (await client.patch(f"{case['path']}/edit-lock")).status_code == 200
