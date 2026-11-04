from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid5

import pytest
import sqlparse
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from src.core.uuid7 import uuid7
from tests.document_requests import create_delivery, patch_with_revision
from tests.helpers import unique_product_name
from tests.integration.api.test_delivery_document_contract import read_events
from tests.integration.api.test_delivery_document_routers import TestDeliveryDocumentRouters as API


async def test_row_identity_migration_preserves_audit_uuid_and_guards_downgrade(postgres):
    folder = Path(
        "src/common/infra/db/postgres/alembic/migrations/versions/2026-11-04_10-00_item_identity_7d1f4e09ac32"
    )
    async with postgres.session_factory() as session:

        async def script(name):
            for statement in sqlparse.split((folder / name).read_text(encoding="utf-8")):
                await session.execute(text(statement))

        await session.execute(
            text(
                "CREATE TEMP TABLE delivery_document_items ("
                "point_id uuid, product_id uuid, is_free_price boolean NOT NULL DEFAULT false, "
                "PRIMARY KEY (point_id, product_id)) ON COMMIT DROP"
            )
        )
        point, product = UUID(int=1), UUID(int=2)
        await session.execute(
            text("INSERT INTO delivery_document_items (point_id, product_id) VALUES (:p, :i)"),
            {"p": point, "i": product},
        )
        await script("upgrade.sql")
        assert await session.scalar(text("SELECT item_id FROM delivery_document_items")) == uuid5(point, str(product))
        await script("downgrade.sql")
        assert await session.scalar(text("SELECT count(*) FROM delivery_document_items")) == 1
        await script("upgrade.sql")
        with pytest.raises(DBAPIError):
            async with session.begin_nested():
                await session.execute(
                    text("INSERT INTO delivery_document_items (point_id, product_id) VALUES (:p, :i)"),
                    {"p": point, "i": product},
                )
        await session.execute(text("UPDATE delivery_document_items SET is_free_price = true"))
        await session.execute(
            text("INSERT INTO delivery_document_items (point_id, product_id, is_free_price) VALUES (:p, :i, true)"),
            {"p": point, "i": product},
        )
        assert await session.scalar(text("SELECT count(*) FROM delivery_document_items")) == 2
        with pytest.raises(DBAPIError, match="Cannot downgrade"):
            async with session.begin_nested():
                await script("downgrade.sql")
        await session.rollback()


async def test_independent_free_rows_memo_precision_report_and_audit(client, active_employee, client_factory, postgres):
    await API.login(client, active_employee)
    customer = await client_factory()
    product = (
        await client.post(
            "/protected/products/create",
            json={
                "name": unique_product_name("repeat-service"),
                "basePrice": 0,
                "isFreePrice": True,
            },
        )
    ).json()["data"]
    ordinary = await API.create_product(client, unique_product_name("ordinary-zero"))
    line = {
        "productId": product["productId"],
        "productName": product["name"],
        "isFreePrice": True,
        "quantity": 2,
        "price": "1.005",
        "driverNote": "Первая",
    }
    response = await create_delivery(
        client,
        json={
            "plannedDate": "2194-09-12",
            "points": [
                {
                    "clientId": str(customer.client_id),
                    "memo": "  Памятка  ",
                    "items": [
                        line,
                        {**line, "price": 0, "quantity": 7, "driverNote": "Вторая"},
                        {
                            "productId": ordinary["productId"],
                            "productName": ordinary["name"],
                            "quantity": 1,
                            "price": 0,
                        },
                    ],
                }
            ],
        },
    )
    assert response.status_code == 201, response.text
    document = response.json()["data"]
    point = document["points"][0]
    assert point["memo"] == "Памятка"
    assert len({row["itemId"] for row in point["items"]}) == 3
    first = next(row for row in point["items"] if row["driverNote"] == "Первая")
    second = next(row for row in point["items"] if row["driverNote"] == "Вторая")
    ordinary_row = next(row for row in point["items"] if not row["isFreePrice"])
    path = f"/protected/delivery-route-sheets/{document['deliveryDocumentId']}"
    assert (await client.post(f"{path}/edit-lock")).status_code == 200
    params = {"date_from": "2194-09-12", "date_to": "2194-09-12"}
    report = (await client.get("/protected/sales-report", params=params)).json()["data"]
    assert report["totalQuantity"] == 3
    assert Decimal(report["totalAmount"]) == Decimal("2.01")

    # Reorder the same product rows and change just one: row IDs, not product IDs, select the target.
    payload = {
        "pointId": point["pointId"],
        "clientId": point["clientId"],
        "items": [second, {**first, "price": "2.005", "driverNote": "Изменена"}, ordinary_row],
    }
    response = await patch_with_revision(client, path, json={"points": [payload]})
    assert response.status_code == 200, response.text
    saved = (await client.get(path)).json()["data"]["points"][0]
    assert saved["memo"] == "Памятка"
    by_id = {row["itemId"]: row for row in saved["items"]}
    assert by_id[first["itemId"]]["driverNote"] == "Изменена"
    assert by_id[first["itemId"]]["price"] == 2.005
    assert by_id[second["itemId"]] == second

    # Explicit null itemId is a new row, never an update of an existing same-product row.
    payload["items"] = [*saved["items"], {**line, "itemId": None, "driverNote": "Третья"}]
    payload["memo"] = ""
    response = await patch_with_revision(client, path, json={"points": [payload]})
    assert response.status_code == 200, response.text
    saved = response.json()["data"]["points"][0]
    assert len(saved["items"]) == 4
    assert saved["memo"] == ""
    payload["items"] = [row for row in saved["items"] if row["itemId"] != second["itemId"]]
    assert (await patch_with_revision(client, path, json={"points": [payload]})).status_code == 200
    loaded = (await client.get(path)).json()["data"]["points"][0]
    assert len(loaded["items"]) == 3
    assert second["itemId"] not in {row["itemId"] for row in loaded["items"]}
    # Reject ambiguous legacy updates, duplicate IDs and IDs from outside this point atomically.
    before_invalid = (await client.get(path)).json()["data"]
    for invalid_rows in [
        [{k: v for k, v in row.items() if k != "itemId"} for row in loaded["items"]],
        [loaded["items"][0], loaded["items"][0]],
        [{**loaded["items"][0], "itemId": str(uuid7())}],
    ]:
        invalid = await patch_with_revision(client, path, json={"points": [{**payload, "items": invalid_rows}]})
        assert invalid.status_code == 422, invalid.text
        assert (await client.get(path)).json()["data"] == before_invalid
    # Deleting and re-adding an ordinary product before Save creates a new row without a transient unique violation.
    payload["items"] = [{**row, "itemId": None} if not row["isFreePrice"] else row for row in loaded["items"]]
    replaced = await patch_with_revision(client, path, json={"points": [payload]})
    assert replaced.status_code == 200, replaced.text
    loaded = replaced.json()["data"]["points"][0]
    assert next(row for row in loaded["items"] if not row["isFreePrice"])["itemId"] != ordinary_row["itemId"]
    # Catalog changes must not change snapshots already stored in a route.
    changed_catalog = await client.patch(
        f"/protected/products/{product['productId']}", json={"isFreePrice": False, "basePrice": 50}
    )
    assert changed_catalog.status_code == 200
    payload["items"] = loaded["items"]
    assert (await patch_with_revision(client, path, json={"points": [payload]})).status_code == 200
    assert all(
        row["isFreePrice"]
        for row in (await client.get(path)).json()["data"]["points"][0]["items"]
        if row["productId"] == product["productId"]
    )
    async with postgres.session_factory() as session:
        price = await session.scalar(
            text("SELECT price FROM delivery_document_items WHERE item_id = :id"), {"id": UUID(first["itemId"])}
        )
        assert price == Decimal("2.005")
    events = await read_events(postgres, document)
    assert any("memo" in event["payload"].get("changes", {}) for event in events)
    assert any("driver_note" in event["payload"].get("changes", {}) for event in events)
    history = (
        await client.get("/protected/delivery-history", params={**params, "search": customer.client.name})
    ).json()
    rows = history["data"]["documents"][0]["matchedClients"][0]["items"]
    assert any(row["itemId"] == first["itemId"] and row["driverNote"] == "Изменена" for row in rows)


async def test_memo_length_clear_preserve_and_creation_retry(client, active_employee, client_factory):
    await API.login(client, active_employee)
    customer = await client_factory()
    payload = {
        "creationRequestId": str(uuid7()),
        "plannedDate": "2194-09-13",
        "points": [{"clientId": str(customer.client_id), "memo": "  Вход со двора ", "items": []}],
    }
    response = await create_delivery(client, json=payload)
    assert response.status_code == 201, response.text
    document = response.json()["data"]
    retry = {**payload, "driverId": document["driverId"], "carId": document["carId"], "startMileage": 0}
    retry["points"][0]["memo"] = "Вход со двора"
    repeated = await client.post("/protected/delivery-route-sheets/create", json=retry)
    assert repeated.status_code == 201
    assert repeated.json()["data"]["deliveryDocumentId"] == document["deliveryDocumentId"]
    retry["points"][0]["memo"] = "Другой текст"
    assert (await client.post("/protected/delivery-route-sheets/create", json=retry)).status_code == 422
    path = f"/protected/delivery-route-sheets/{document['deliveryDocumentId']}"
    assert (await client.post(f"{path}/edit-lock")).status_code == 200
    point = document["points"][0]
    body = {"pointId": point["pointId"], "clientId": point["clientId"], "items": []}
    for extra, expected in [({}, "Вход со двора"), ({"memo": "Новая"}, "Новая"), ({"memo": ""}, "")]:
        saved = await patch_with_revision(client, path, json={"points": [{**body, **extra}]})
        assert saved.status_code == 200, saved.text
        assert saved.json()["data"]["points"][0]["memo"] == expected
    assert (await patch_with_revision(client, path, json={"points": [{**body, "memo": "x" * 1001}]})).status_code == 422
