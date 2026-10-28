import asyncio
from datetime import datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from src.common.infra.services.event_pud_service import EventPublisher
from src.core.uuid7 import uuid7
from tests.document_requests import patch_with_revision
from tests.helpers import delivery_address, unique_car_number, unique_phone, unique_product_name
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
                "deliveryAddress": delivery_address(),
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
            "items": [
                {key: item[key] for key in ("productId", "productName", "quantity", "price")} for item in point["items"]
            ],
        }
        for point in document["points"]
    ]


async def test_free_address_details_and_manual_order_without_coordinates(client, document_case):
    case = document_case
    customer = case["customers"][0]
    response = await patch_with_revision(
        client,
        f"/protected/clients/{customer['clientId']}",
        json={
            "address": "Произвольный адрес без карты",
            "deliveryDetails": "Позвонить у ворот",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["deliveryAddress"] is None
    document = (await client.get(case["path"])).json()["data"]
    point = next(p for p in document["points"] if p["clientId"] == customer["clientId"])
    assert point["address"] == "Произвольный адрес без карты — Позвонить у ворот"
    reordered = patch_points(document)[::-1]
    saved = await patch_with_revision(client, case["path"], json={"points": reordered})
    assert saved.status_code == 200, saved.text
    fetched = (await client.get(case["path"])).json()["data"]
    assert [p["clientId"] for p in fetched["points"]] == [p["clientId"] for p in reordered]


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
    response = await patch_with_revision(client, case["path"], json={"points": points})
    assert response.status_code == 200
    loaded = (await client.get(case["path"])).json()["data"]
    assert len(loaded["points"]) == 2
    assert all(point["items"] == [] for point in loaded["points"])
    response = await patch_with_revision(client, case["path"], json={"points": []})
    assert response.status_code == 200
    assert (await client.get(case["path"])).json()["data"]["points"] == []
    response = await patch_with_revision(client, case["path"], json={"points": points})
    assert response.status_code == 422  # Deleted point IDs cannot be reused.


async def test_existing_inactive_references_and_new_rows(client: AsyncClient, document_case) -> None:
    case = document_case
    customer_id = case["customers"][0]["clientId"]
    product_id = case["product"]["productId"]
    for resource, resource_id in (("clients", customer_id), ("products", product_id)):
        assert (
            await patch_with_revision(client, f"/protected/{resource}/{resource_id}", json={"isActive": False})
        ).status_code == 200
    points = patch_points(case["document"])
    points[0]["items"][0].update(quantity=7, price=0.0)
    response = await patch_with_revision(client, case["path"], json={"points": points})
    assert response.status_code == 200
    saved = response.json()["data"]
    assert saved["points"][0]["items"][0]["quantity"] == 7
    assert saved["points"][0]["items"][0]["price"] == 0.0
    # Inactivity is checked for a new item in each point, not globally per document.
    bad_points = patch_points(saved)
    bad_points[1]["items"] = [{"productName": "Товар", "productId": product_id, "quantity": 1, "price": 99.0}]
    response = await patch_with_revision(client, case["path"], json={"plannedDate": "2025-04-01", "points": bad_points})
    assert response.status_code == 422
    assert (await client.get(case["path"])).json()["data"] == saved
    # Replacing an existing point for an inactive customer constitutes a new link.
    bad_points = patch_points(saved)
    bad_points[0].pop("pointId")
    bad_points[0]["items"] = []
    assert (await patch_with_revision(client, case["path"], json={"points": bad_points})).status_code == 422
    assert (await client.get(case["path"])).json()["data"] == saved
    for point in (
        {"clientId": customer_id, "items": []},
        DeliveryAPI.point_payload(case["customers"][1]["clientId"], product_id),
    ):
        response = await client.post(f"{case['base']}/create", json={**case["payload"], "points": [point]})
        assert response.status_code == 422
    assert (
        await patch_with_revision(client, f"/protected/products/{product_id}", json={"isActive": True})
    ).status_code == 200
    points = patch_points(saved)
    points[1]["items"] = [{"productName": "Товар", "productId": product_id, "quantity": 1, "price": 99.0}]
    assert (await patch_with_revision(client, case["path"], json={"points": points})).status_code == 200


async def test_client_identity_and_point_replacement_are_atomic(client: AsyncClient, document_case, postgres) -> None:
    case = document_case
    saved = case["document"]
    events = await read_events(postgres, saved)
    points = patch_points(saved)
    points[0]["clientId"] = case["customers"][1]["clientId"]
    points = points[:1]
    response = await patch_with_revision(client, case["path"], json={"plannedDate": "2025-04-01", "points": points})
    assert response.status_code == 422
    assert (await client.get(case["path"])).json()["data"] == saved
    assert await read_events(postgres, saved) == events
    points = patch_points(saved)
    # Re-create a point for the same client while reversing order.
    points[0].pop("pointId")
    response = await patch_with_revision(client, case["path"], json={"points": list(reversed(points))})
    assert response.status_code == 200
    loaded = (await client.get(case["path"])).json()["data"]
    assert [point["clientId"] for point in loaded["points"]] == [p["clientId"] for p in reversed(saved["points"])]
    assert [point["position"] for point in loaded["points"]] == [0, 1]
    assert loaded["points"][1]["pointId"] != saved["points"][0]["pointId"]
    assert loaded["points"][1]["items"] == saved["points"][0]["items"]
    events = await read_events(postgres, saved)
    deleted = next(event for event in events if event["event_type"] == "DeletePointEvent")
    assert deleted["payload"]["data"]["client_id"] == {
        "id": saved["points"][0]["clientId"],
        "display_name": saved["points"][0]["clientName"],
    }
    assert deleted["payload"]["data"]["items"][0]["price"] == 12.5
    assert any(event["event_type"] == "DeleteItemEvent" for event in events)


async def test_cancel_removes_own_lock_and_restore_preserves_data(
    client: AsyncClient, document_case, active_employee, postgres
) -> None:
    case = document_case
    response = await client.post(f"{case['path']}/cancel")
    assert response.status_code == 200
    cancelled = response.json()["data"]
    assert cancelled == {**case["document"], "isActive": False, "revision": case["document"]["revision"] + 1}
    for method in (client.post, client.patch):
        response = await method(f"{case['path']}/edit-lock")
        assert response.status_code == 409
        assert response.json() == {"detail": "Delivery document is cancelled"}
    assert (await client.delete(f"{case['path']}/edit-lock")).status_code == 409
    assert (await patch_with_revision(client, case["path"], json={"points": []})).status_code == 422
    assert (await client.post(f"{case['path']}/restore")).json()["data"] == {
        **case["document"],
        "revision": case["document"]["revision"] + 2,
    }
    assert (await patch_with_revision(client, case["path"], json={"points": []})).status_code == 409
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
    response = await patch_with_revision(client, case["path"], json={"points": []})
    assert response.status_code == 423
    assert response.json()["ownerName"] == active_employee.username
    assert (await client.get(case["path"])).json()["data"] == case["document"]
    assert (await patch_with_revision(client, f"{case['path']}/edit-lock")).status_code == 403
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
    assert (await patch_with_revision(client, f"{case['path']}/edit-lock")).status_code == 409
    assert (await client.delete(f"{case['path']}/edit-lock")).status_code == 409
    assert (await patch_with_revision(client, case["path"], json={"points": []})).status_code == 409
    other = await employee_factory()
    await DeliveryAPI.login(client, other)
    response = await client.post(f"{case['path']}/edit-lock")
    assert response.status_code == 200
    assert response.json()["data"]["ownerName"] == other.username
    assert (await patch_with_revision(client, case["path"], json={"points": []})).status_code == 200


async def test_history_records_root_and_children(client: AsyncClient, document_case, postgres, active_employee) -> None:
    case = document_case
    events = await read_events(postgres, case["document"])
    assert all(str(event["actor_id"]) == str(active_employee.employee_id) for event in events)
    created = next(event["payload"] for event in events if event["event_type"] == "CreateDeliveryDocumentEvent")
    assert created["data"]["planned_date"] == "2025-03-15"
    assert created["data"]["points"][0]["items"][0]["price"] == 12.5
    points = patch_points(case["document"])
    points[0]["items"][0].update(quantity=3, price=15.0)
    assert (await patch_with_revision(client, case["path"], json={"points": points})).status_code == 200
    events = await read_events(postgres, case["document"])
    item = next(event["payload"] for event in events if event["event_type"] == "UpdateItemEvent")
    assert item["changes"]["quantity"] == {"old": 2, "new": 3}
    assert item["changes"]["price"] == {"old": 12.5, "new": 15.0}
    assert any(event["event_type"] == "UpdatePointEvent" for event in events)
    root = next(event["payload"] for event in events if event["event_type"] == "UpdateDeliveryDocumentEvent")
    assert root["changes"]["points"]["old"][0]["items"][0]["quantity"] == 2
    assert root["changes"]["points"]["new"][0]["items"][0]["quantity"] == 3
    count = len(events)
    assert (await patch_with_revision(client, case["path"], json={"points": points})).status_code == 200
    assert len(await read_events(postgres, case["document"])) == count


@pytest.mark.parametrize("resource", ["drivers", "cars"])
@pytest.mark.parametrize("document_case", [DELIVERY_BASE_PATH], indirect=True)
async def test_inactive_assignment_can_be_retained_but_not_changed(
    client: AsyncClient, document_case, resource
) -> None:
    case = document_case
    document = case["document"]
    resource_id = document["driverId" if resource == "drivers" else "carId"]
    assert (
        await patch_with_revision(client, f"/protected/{resource}/{resource_id}", json={"isActive": False})
    ).status_code == 200
    response = await patch_with_revision(
        client,
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
    response = await patch_with_revision(client, case["path"], json={"plannedDate": "2025-04-01"})
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
    assert (await patch_with_revision(client, case["path"], json=changed_assignment)).status_code == 422
    assert (await client.get(case["path"])).json()["data"] == saved
    response = await client.post(f"{case['base']}/create", json=case["payload"])
    assert response.status_code == 422
    assert (
        await patch_with_revision(client, f"/protected/{resource}/{resource_id}", json={"isActive": True})
    ).status_code == 200
    assert (await patch_with_revision(client, case["path"], json={"plannedDate": "2025-04-01"})).status_code == 200


@pytest.mark.parametrize("document_case", [DELIVERY_BASE_PATH], indirect=True)
async def test_mileage_validates_combined_state_and_explicit_null(client: AsyncClient, document_case) -> None:
    path = document_case["path"]
    assert (await patch_with_revision(client, path, json={"endMileage": 200.0})).status_code == 200
    saved = (await client.get(path)).json()["data"]
    assert (await patch_with_revision(client, path, json={"startMileage": 201.0})).status_code == 422
    assert (await client.get(path)).json()["data"] == saved
    assert (await patch_with_revision(client, path, json={"endMileage": None})).status_code == 200
    assert (await client.get(path)).json()["data"]["endMileage"] is None
    for field in ("plannedDate", "driverId", "carId", "startMileage", "points"):
        assert (await patch_with_revision(client, path, json={field: None})).status_code == 422
    assert (await patch_with_revision(client, path, json={"startMileage": -1})).status_code == 422


@pytest.mark.parametrize("document_case", [DELIVERY_BASE_PATH], indirect=True)
async def test_mileage_sync_preserves_newer_readings_and_manual_corrections(client, document_case) -> None:
    case = document_case
    car_path = f"/protected/cars/{case['document']['carId']}"
    assert (await patch_with_revision(client, case["path"], json={"endMileage": 200})).status_code == 200
    assert (await client.get(car_path)).json()["data"]["currentMileage"] == 200
    # An unrelated save does not undo a user's explicit odometer correction.
    assert (await patch_with_revision(client, car_path, json={"currentMileage": 150})).status_code == 200
    assert (await patch_with_revision(client, case["path"], json={"endMileage": 200, "points": []})).status_code == 200
    assert (await client.get(car_path)).json()["data"]["currentMileage"] == 150
    # Historical lower readings remain in the document but never rewind the car.
    assert (await patch_with_revision(client, case["path"], json={"endMileage": 120})).status_code == 200
    assert (await client.get(car_path)).json()["data"]["currentMileage"] == 150
    assert (await patch_with_revision(client, case["path"], json={"endMileage": None})).status_code == 200
    assert (await client.post(f"{case['path']}/cancel")).status_code == 200
    assert (await client.post(f"{case['path']}/restore")).status_code == 200
    assert (await client.get(car_path)).json()["data"]["currentMileage"] == 150


@pytest.mark.parametrize("document_case", [DELIVERY_BASE_PATH], indirect=True)
async def test_zero_distance_and_sequential_trips_update_car(client, document_case) -> None:
    case = document_case
    car_path = f"/protected/cars/{case['document']['carId']}"
    zero = await client.post(f"{case['base']}/create", json={**case["payload"], "endMileage": 100})
    assert zero.status_code == 201
    assert (await client.get(car_path)).json()["data"]["currentMileage"] == 100
    assert (await patch_with_revision(client, case["path"], json={"endMileage": 200})).status_code == 200
    evening = await client.post(
        f"{case['base']}/create", json={**case["payload"], "startMileage": 200, "endMileage": 300}
    )
    assert evening.status_code == 201
    assert (await client.get(car_path)).json()["data"]["currentMileage"] == 300
    assert (await client.get(case["path"])).json()["data"]["startMileage"] == 100


@pytest.mark.parametrize("correction", [None, 90.0, 450.0])
@pytest.mark.parametrize("document_case", [DELIVERY_BASE_PATH], indirect=True)
async def test_recorded_car_replacement_is_atomic_and_audited(client, postgres, document_case, correction) -> None:
    case = document_case
    old_id = case["document"]["carId"]
    assert (await patch_with_revision(client, case["path"], json={"endMileage": 200})).status_code == 200
    new_car = (
        await client.post(
            "/protected/cars/create",
            json={"model": "Replacement", "number": unique_car_number(), "currentMileage": 500},
        )
    ).json()["data"]
    payload = {"carId": new_car["carId"], "startMileage": 500, "endMileage": None}
    assert (await patch_with_revision(client, case["path"], json=payload)).status_code == 422
    assert (await client.get(case["path"])).json()["data"]["carId"] == old_id
    payload["carChangeConfirmed"] = True
    if correction is not None:
        payload["previousCarMileage"] = correction
    response = await patch_with_revision(client, case["path"], json=payload)
    assert response.status_code == 200
    loaded = (await client.get(case["path"])).json()["data"]
    assert loaded["carId"] == new_car["carId"]
    assert loaded["startMileage"] == 500
    assert loaded["endMileage"] is None
    assert (await client.get(f"/protected/cars/{old_id}")).json()["data"]["currentMileage"] == (
        200 if correction is None else correction
    )
    assert (await client.get(f"/protected/cars/{new_car['carId']}")).json()["data"]["currentMileage"] == 500
    if correction is not None:
        async with postgres.session_factory() as session:
            result = await session.execute(
                text("SELECT payload FROM events WHERE payload->>'car_id' = :id AND event_type = 'UpdateCarEvent'"),
                {"id": old_id},
            )
            assert any(row[0]["changes"]["current_mileage"] == {"old": 200, "new": correction} for row in result)
    assert (await patch_with_revision(client, case["path"], json={"previousCarMileage": 0})).status_code == 422


@pytest.mark.parametrize("document_case", [DELIVERY_BASE_PATH], indirect=True)
async def test_car_mileage_rolls_back_with_document_on_event_failure(client, document_case, monkeypatch) -> None:
    case = document_case
    old_id = case["document"]["carId"]
    assert (await patch_with_revision(client, case["path"], json={"endMileage": 200})).status_code == 200
    new_car = (
        await client.post(
            "/protected/cars/create",
            json={"model": "Rollback", "number": unique_car_number(), "currentMileage": 500},
        )
    ).json()["data"]

    async def fail_publish(*args, **kwargs):
        raise RuntimeError("test event failure")

    with monkeypatch.context() as patch:
        patch.setattr(EventPublisher, "publish_many", fail_publish)
        with pytest.raises(RuntimeError, match="test event failure"):
            await patch_with_revision(
                client,
                case["path"],
                json={
                    "carId": new_car["carId"],
                    "startMileage": 500,
                    "endMileage": 600,
                    "carChangeConfirmed": True,
                    "previousCarMileage": 90,
                },
            )
    assert (await client.get(case["path"])).json()["data"]["carId"] == old_id
    assert (await client.get(f"/protected/cars/{old_id}")).json()["data"]["currentMileage"] == 200
    assert (await client.get(f"/protected/cars/{new_car['carId']}")).json()["data"]["currentMileage"] == 500


@pytest.mark.parametrize("document_case", [DELIVERY_BASE_PATH], indirect=True)
async def test_concurrent_trip_saves_keep_highest_car_mileage(client, document_case) -> None:
    case = document_case
    other = (await client.post(f"{case['base']}/create", json=case["payload"])).json()["data"]
    other_path = f"{case['base']}/{other['deliveryDocumentId']}"
    assert (await client.post(f"{other_path}/edit-lock")).status_code == 200
    responses = await asyncio.gather(
        patch_with_revision(client, case["path"], json={"endMileage": 400}),
        patch_with_revision(client, other_path, json={"endMileage": 300}),
    )
    assert [r.status_code for r in responses] == [200, 200]
    assert (await client.get(f"/protected/cars/{case['document']['carId']}")).json()["data"]["currentMileage"] == 400


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
            else patch_with_revision(client, case["path"], json={"plannedDate": "2025-04-01", "points": []})
        )
        with pytest.raises(RuntimeError, match="Simulated event persistence failure"):
            await request
    assert (await client.get(case["path"])).json()["data"] == case["document"]
    assert await read_events(postgres, case["document"]) == previous_events
    assert (await patch_with_revision(client, f"{case['path']}/edit-lock")).status_code == 200


async def test_product_name_is_client_snapshot_and_immutable(client: AsyncClient, document_case, postgres) -> None:
    case = document_case
    product_id = case["product"]["productId"]
    catalog_name = unique_product_name("renamed_catalog")
    response = await patch_with_revision(client, f"/protected/products/{product_id}", json={"name": catalog_name})
    assert response.status_code == 200
    historical_name = "  Вода Горная / 19 л  "
    # Simulate a selection made before a concurrent catalog rename.
    payload = {
        **case["payload"],
        "points": [
            DeliveryAPI.point_payload(case["customers"][0]["clientId"], product_id, product_name=historical_name),
        ],
    }
    response = await client.post(f"{case['base']}/create", json=payload)
    assert response.status_code == 201
    saved = response.json()["data"]
    path = f"{case['base']}/{saved['deliveryDocumentId']}"
    assert saved["points"][0]["items"][0]["productName"] == historical_name
    assert (await client.post(f"{path}/edit-lock")).status_code == 200

    response = await patch_with_revision(
        client, f"/protected/products/{product_id}", json={"name": unique_product_name("renamed_again")}
    )
    assert response.status_code == 200
    assert (await client.get(path)).json()["data"] == saved
    events = await read_events(postgres, saved)
    created = next(event for event in events if event["event_type"] == "CreateItemEvent")
    assert created["payload"]["data"]["product_name"] == historical_name
    root = next(event for event in events if event["event_type"] == "CreateDeliveryDocumentEvent")
    assert root["payload"]["data"]["points"][0]["items"][0]["product_name"] == historical_name

    points = patch_points(saved)
    points[0]["items"][0].update(productName=catalog_name, quantity=7, price=45.0)
    response = await patch_with_revision(client, path, json={"points": points})
    assert response.status_code == 200
    saved = response.json()["data"]
    assert saved["points"][0]["items"] == [
        {"productId": product_id, "productName": historical_name, "quantity": 7, "price": 45.0},
    ]
    events = await read_events(postgres, saved)
    updated = next(event for event in events if event["event_type"] == "UpdateItemEvent")
    assert updated["payload"]["changes"] == {"quantity": {"old": 2, "new": 7}, "price": {"old": 100.0, "new": 45.0}}
    root_update = next(event for event in events if event["event_type"] == "UpdateDeliveryDocumentEvent")
    for state in ("old", "new"):
        assert root_update["payload"]["changes"]["points"][state][0]["items"][0]["product_name"] == historical_name
    # A name-only edit is ignored and must not create history for a nonexistent change.
    assert (await patch_with_revision(client, path, json={"points": points})).status_code == 200
    assert (await client.get(path)).json()["data"] == saved
    assert await read_events(postgres, saved) == events

    assert (
        await patch_with_revision(client, f"/protected/products/{product_id}", json={"isActive": False})
    ).status_code == 200
    points[0]["items"][0].update(quantity=8, price=0.0)
    response = await patch_with_revision(client, path, json={"points": points})
    assert response.status_code == 200
    assert response.json()["data"]["points"][0]["items"][0]["productName"] == historical_name
    for suffix, active in (("cancel", False), ("restore", True)):
        response = await client.post(f"{path}/{suffix}")
        assert response.status_code == 200
        assert response.json()["data"]["isActive"] is active
        assert response.json()["data"]["points"][0]["items"][0]["productName"] == historical_name
    assert (await client.post(f"{path}/edit-lock")).status_code == 200
    assert (
        await patch_with_revision(client, f"/protected/products/{product_id}", json={"isActive": True})
    ).status_code == 200
    points[0]["items"] = []
    assert (await patch_with_revision(client, path, json={"points": points})).status_code == 200
    points[0]["items"] = [{"productId": product_id, "productName": catalog_name, "quantity": 1, "price": 99.0}]
    response = await patch_with_revision(client, path, json={"points": points})
    assert response.status_code == 200
    readded = response.json()["data"]
    assert readded["points"][0]["pointId"] == saved["points"][0]["pointId"]
    assert readded["points"][0]["items"][0]["productName"] == catalog_name
    events = await read_events(postgres, readded)
    deleted = next(event for event in events if event["event_type"] == "DeleteItemEvent")
    assert deleted["payload"]["data"]["product_name"] == historical_name
    created_items = [event for event in events if event["event_type"] == "CreateItemEvent"]
    assert [event["payload"]["data"]["product_name"] for event in created_items] == [historical_name, catalog_name]


@pytest.mark.parametrize("invalid_name", [None, "", "x" * 121, 123])
async def test_product_name_validation_is_atomic(client: AsyncClient, document_case, postgres, invalid_name) -> None:
    case = document_case
    saved = case["document"]
    events = await read_events(postgres, saved)
    points = patch_points(saved)
    points[0]["items"][0]["quantity"] = 77
    # A later, invalid row prevents all document changes, including earlier valid rows.
    points[1]["items"] = [
        {"productId": case["product"]["productId"], "productName": invalid_name, "quantity": 1, "price": 0.0}
    ]
    response = await patch_with_revision(client, case["path"], json={"plannedDate": "2025-04-01", "points": points})
    assert response.status_code == 422
    assert (await client.get(case["path"])).json()["data"] == saved
    assert await read_events(postgres, saved) == events
    response = await client.post(f"{case['base']}/create", json={**case["payload"], "points": [points[1]]})
    assert response.status_code == 422


async def test_product_name_is_required_and_accepts_120_characters(client: AsyncClient, document_case) -> None:
    case = document_case
    points = patch_points(case["document"])
    points[0]["items"][0].pop("productName")
    assert (await patch_with_revision(client, case["path"], json={"points": points})).status_code == 422
    assert (await client.post(f"{case['base']}/create", json={**case["payload"], "points": points})).status_code == 422
    name = "Ж" * 120
    points[0]["items"][0]["productName"] = name
    response = await client.post(f"{case['base']}/create", json={**case["payload"], "points": points})
    assert response.status_code == 201
    assert response.json()["data"]["points"][0]["items"][0]["productName"] == name


async def test_stale_revision_cannot_overwrite_document(client, document_case):
    case = document_case
    version = case["document"]["revision"]
    operation = str(uuid7())
    response = await client.patch(
        case["path"], json={"expectedRevision": version, "operationId": operation, "plannedDate": "2025-04-02"}
    )
    assert response.status_code == 200, response.text
    saved = response.json()["data"]
    assert saved["revision"] == version + 1
    assert saved["lastOperationId"] == operation
    # Even after releasing and reacquiring the lock, an old editor cannot save.
    assert (await client.delete(f"{case['path']}/edit-lock")).status_code == 200
    assert (await client.post(f"{case['path']}/edit-lock")).status_code == 200
    stale = await client.patch(case["path"], json={"expectedRevision": version, "points": []})
    assert stale.status_code == 409
    assert stale.json()["code"] == "document_revision_conflict"
    assert (await client.get(case["path"])).json()["data"] == saved


async def test_document_patch_requires_revision(client, document_case):
    response = await client.patch(document_case["path"], json={"points": []})
    assert response.status_code == 422
    assert (await client.get(document_case["path"])).json()["data"] == document_case["document"]


async def test_concurrent_saves_accept_only_one_revision(client, document_case):
    case = document_case
    version = case["document"]["revision"]
    responses = await asyncio.gather(
        *(
            client.patch(case["path"], json={"expectedRevision": version, "plannedDate": day})
            for day in ("2025-05-01", "2025-05-02")
        )
    )
    assert sorted(r.status_code for r in responses) == [200, 409]
    current = (await client.get(case["path"])).json()["data"]
    assert current["revision"] == version + 1


async def test_creation_retry_and_lookup_do_not_duplicate_document(client, document_case):
    case = document_case
    request_id = str(uuid7())
    path = f"{case['base']}/creation-requests/{request_id}"
    assert (await client.get(path)).status_code == 404
    payload = {**case["payload"], "creationRequestId": request_id}
    responses = await asyncio.gather(*(client.post(f"{case['base']}/create", json=payload) for _ in range(2)))
    assert [r.status_code for r in responses] == [201, 201]
    first, second = (r.json()["data"] for r in responses)
    assert first == second
    assert first["revision"] == 1
    assert first["lastOperationId"] == request_id
    assert (await client.get(path)).json()["data"] == first
    changed_retry = await client.post(f"{case['base']}/create", json={**payload, "plannedDate": "2025-07-02"})
    assert changed_retry.status_code == 422
    assert (await client.get(path)).json()["data"] == first


async def test_lock_operations_do_not_change_revision(client, document_case):
    case = document_case
    assert (await client.patch(f"{case['path']}/edit-lock")).status_code == 200
    assert (await client.delete(f"{case['path']}/edit-lock")).status_code == 200
    assert (await client.post(f"{case['path']}/edit-lock")).status_code == 200
    assert (await client.get(case["path"])).json()["data"] == case["document"]
