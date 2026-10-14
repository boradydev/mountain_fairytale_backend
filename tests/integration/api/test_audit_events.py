import json

import pytest
from sqlalchemy import text

from src.common.infra.services.event_pud_service import EventPublisher
from tests.helpers import unique_product_name
from tests.integration.api.test_delivery_document_contract import document_case as _document_case


document_case = _document_case


async def login(client, employee):
    response = await client.post(
        "/public/auth/login", json={"username": employee.username, "password": employee.password}
    )
    assert response.status_code == 200
    return response.json()["data"]


async def create_product(client, name):
    response = await client.post("/protected/products/create", json={"name": name, "basePrice": 100})
    assert response.status_code == 201
    return response.json()["data"]


async def test_history_current_actor_and_changed_fields(client, admin_employee):
    await login(client, admin_employee)
    name = unique_product_name("audit")
    product = await create_product(client, name)
    path = f"/protected/products/{product['productId']}"
    assert (await client.patch(path, json={"name": name + " renamed", "basePrice": 120})).status_code == 200
    assert (await client.patch(path, json={"basePrice": 120})).status_code == 200
    assert (await client.patch(path, json={"isActive": False})).status_code == 200
    renamed_actor = admin_employee.username + "_new"
    response = await client.patch(f"/admin/employees/{admin_employee.employee_id}", json={"username": renamed_actor})
    assert response.status_code == 200
    response = await client.get("/protected/events", params={"search": name})
    assert response.status_code == 200
    events = response.json()["data"]["events"]
    assert [e["action"] for e in events] == ["deactivated", "updated", "created"]
    assert all(e["actor"]["displayName"] == renamed_actor for e in events)
    assert all(e["actor"]["actorId"] == str(admin_employee.employee_id) for e in events)
    assert events[-1]["subject"]["displayName"] == name
    assert events[-1]["data"]["name"] == name
    assert events[0]["subject"]["displayName"] == name + " renamed"
    assert events[1]["changes"] == {
        "name": {"oldValue": name, "newValue": name + " renamed"},
        "basePrice": {"oldValue": 100, "newValue": 120},
    }
    assert events[0]["changes"] == {"isActive": {"oldValue": True, "newValue": False}}
    assert events[0]["createdAt"].endswith("Z")
    assert response.json()["data"]["nextCursor"] is None


async def test_cursor_with_concurrent_insert_and_filter_binding(client, active_employee):
    await login(client, active_employee)
    prefix = unique_product_name("cursor")
    created = [await create_product(client, f"{prefix}-{i}") for i in range(5)]
    first = await client.get("/protected/events", params={"search": prefix, "limit": 2})
    assert first.status_code == 200
    page = first.json()["data"]
    assert page["nextCursor"]
    ids = [e["subject"]["id"] for e in page["events"]]
    await create_product(client, prefix + " newest")
    cursor = page["nextCursor"]
    while cursor:
        response = await client.get("/protected/events", params={"search": prefix, "limit": 2, "cursor": cursor})
        assert response.status_code == 200
        page = response.json()["data"]
        ids.extend(e["subject"]["id"] for e in page["events"])
        cursor = page["nextCursor"]
    assert ids == [p["productId"] for p in reversed(created)]
    invalid = await client.get(
        "/protected/events", params={"search": "other", "cursor": first.json()["data"]["nextCursor"]}
    )
    assert invalid.status_code == 422
    assert (await client.get("/protected/events", params={"cursor": "bad!"})).status_code == 422
    assert (await client.get("/protected/events", params={"limit": 101})).status_code == 422


async def test_login_refresh_and_secret_free_password_event(client, active_employee, postgres):
    tokens = await login(client, active_employee)
    response = await client.post("/public/auth/refresh", json={"refreshToken": tokens["refreshToken"]})
    assert response.status_code == 200
    assert (
        await client.post("/public/auth/login", json={"username": active_employee.username, "password": "wrong"})
    ).status_code == 401
    password = "audit_changed_password"
    assert (await client.put("/protected/me/change-password", json={"password": password})).status_code == 200
    response = await client.get("/protected/events", params={"search": active_employee.username})
    assert response.status_code == 200
    events = response.json()["data"]["events"]
    assert sum(e["action"] == "login" for e in events) == 1
    changed = next(e for e in events if e["action"] == "password_changed")
    assert changed["changes"] == {}
    assert changed["data"] == {}
    async with postgres.session_factory() as session:
        rows = (
            (
                await session.execute(
                    text("SELECT payload FROM events WHERE actor_id=:actor"), {"actor": active_employee.employee_id}
                )
            )
            .scalars()
            .all()
        )
    stored = json.dumps(rows)
    assert "password_hash" not in stored
    assert password not in stored
    assert "access_token" not in stored


async def test_document_operation_and_lock_exclusion(client, document_case, postgres):
    document_id = document_case["document"]["deliveryDocumentId"]
    async with postgres.session_factory() as session:
        operation = await session.scalar(
            text(
                "SELECT operation_id FROM events WHERE payload->>'subject_id'=:id "
                "AND event_type='CreateDeliveryDocumentEvent'"
            ),
            {"id": document_id},
        )
        rows = (
            (
                await session.execute(
                    text("SELECT payload, event_type FROM events WHERE operation_id=:id"), {"id": operation}
                )
            )
            .mappings()
            .all()
        )
        before = await session.scalar(text("SELECT count(*) FROM events"))
    assert len(rows) >= 4
    assert any(row["event_type"] == "CreateItemEvent" for row in rows)
    point = next(row for row in rows if row["event_type"] == "CreatePointEvent")
    assert point["payload"]["data"]["display_name"]
    assert (await client.patch(document_case["path"] + "/edit-lock")).status_code == 200
    assert (await client.delete(document_case["path"] + "/edit-lock")).status_code == 200
    async with postgres.session_factory() as session:
        after = await session.scalar(text("SELECT count(*) FROM events"))
    assert after == before


async def test_requires_authorization(client):
    response = await client.get("/protected/events")
    assert response.status_code == 401


async def test_audit_failure_rolls_back_business_mutation(client, active_employee, monkeypatch):
    await login(client, active_employee)
    name = unique_product_name("rollback")

    async def fail(self, *, events):
        raise RuntimeError("Audit unavailable")

    monkeypatch.setattr(EventPublisher, "publish_many", fail)
    with pytest.raises(RuntimeError, match="Audit unavailable"):
        await client.post("/protected/products/create", json={"name": name, "basePrice": 1})
    response = await client.get("/protected/products")
    assert response.status_code == 200
    assert all(product["name"] != name for product in response.json()["data"]["products"])
