import runpy
from pathlib import Path
from typing import Any

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from src.core.uuid7 import uuid7
from tests.document_requests import create_delivery, patch_with_revision
from tests.helpers import unique_product_name
from tests.integration.api.test_delivery_document_routers import TestDeliveryDocumentRouters as API


async def test_failed_delivery_lifecycle_totals_commissions_and_last_order(
    client,
    active_employee,
    client_factory,
    postgres,
):
    await API.login(client, active_employee)
    customer = await client_factory()
    product = await API.create_product(client, unique_product_name("failed delivery"))
    response = await create_delivery(
        client,
        json={
            "plannedDate": "2194-05-12",
            "points": [API.point_payload(str(customer.client_id), product["productId"], price=12.5)],
        },
    )
    assert response.status_code == 201, response.text
    document = response.json()["data"]
    path = f"/protected/delivery-route-sheets/{document['deliveryDocumentId']}"
    assert (await client.post(f"{path}/edit-lock")).status_code == 200
    point = document["points"][0]
    payload = {
        "pointId": point["pointId"],
        "clientId": point["clientId"],
        "items": point["items"],
        "isDelivered": False,
        "nonDeliveryReason": "  Клиент отсутствует  ",
    }
    response = await patch_with_revision(client, path, json={"points": [payload]})
    assert response.status_code == 200, response.text
    saved = response.json()["data"]["points"][0]
    assert saved["isDelivered"] is False
    assert saved["nonDeliveryReason"] == "Клиент отсутствует"
    assert saved["items"] == point["items"]
    assert (await client.get(path)).json()["data"]["points"][0] == saved
    report_params = {"date_from": "2194-05-12", "date_to": "2194-05-12"}
    assert (await client.get("/protected/sales-report", params=report_params)).json()["data"]["totalAmount"] == "0.00"
    day = await client.get("/protected/delivery-days/2194-05-12/documents")
    assert day.json()["data"]["documents"][0]["points"][0]["isDelivered"] is False
    customer_response = await client.get(f"/protected/clients/{customer.client_id}")
    assert customer_response.json()["data"]["lastOrder"] is None
    history = await client.get("/protected/delivery-history", params={**report_params, "search": customer.client.name})
    attempt = history.json()["data"]["documents"][0]
    assert attempt["totalAmount"] == "0.00"
    assert attempt["matchedClients"][0]["isDelivered"] is False
    assert attempt["matchedClients"][0]["totalAmount"] == "25.00"
    async with postgres.session_factory() as session:
        turnover = await session.scalar(
            text("SELECT turnover FROM point_commissions WHERE point_id = :id"), {"id": point["pointId"]}
        )
        assert turnover == 0
    # Old clients omitting the new fields must preserve the saved outcome.
    omitted = {k: v for k, v in payload.items() if k not in {"isDelivered", "nonDeliveryReason"}}
    response = await patch_with_revision(client, path, json={"points": [omitted]})
    assert response.json()["data"]["points"][0]["isDelivered"] is False
    payload["isDelivered"] = True
    response = await patch_with_revision(client, path, json={"points": [payload]})
    assert response.status_code == 200, response.text
    assert response.json()["data"]["points"][0]["nonDeliveryReason"] == ""
    assert (await client.get("/protected/sales-report", params=report_params)).json()["data"]["totalAmount"] == "25.00"
    customer_response = await client.get(f"/protected/clients/{customer.client_id}")
    assert customer_response.json()["data"]["lastOrder"]["date"] == "2194-05-12"
    payload["isDelivered"] = False
    payload["nonDeliveryReason"] = "   "
    assert (await patch_with_revision(client, path, json={"points": [payload]})).status_code == 422
    assert (await client.get(path)).json()["data"]["points"][0]["isDelivered"] is True


async def test_pickup_cannot_be_marked_failed(client, active_employee):
    await API.login(client, active_employee)
    response = await client.post(
        "/protected/pickup-sheets/create",
        json={
            "plannedDate": "2194-05-13",
            "points": [{"items": [], "isDelivered": False, "nonDeliveryReason": "No pickup"}],
        },
    )
    assert response.status_code == 422, response.text


async def test_creation_retry_checks_delivery_outcome_without_changing_legacy_fingerprint(
    client,
    active_employee,
    client_factory,
):
    await API.login(client, active_employee)
    customer = await client_factory()
    payload: dict[str, Any] = {
        "creationRequestId": str(uuid7()),
        "plannedDate": "2194-05-15",
        "points": [{"clientId": str(customer.client_id), "items": []}],
    }
    response = await create_delivery(client, json=payload)
    assert response.status_code == 201, response.text
    document = response.json()["data"]
    payload.update(driverId=document["driverId"], carId=document["carId"], startMileage=0)
    payload["points"][0].update(isDelivered=True, nonDeliveryReason="")
    retry = await client.post("/protected/delivery-route-sheets/create", json=payload)
    assert retry.status_code == 201, retry.text
    assert retry.json()["data"]["deliveryDocumentId"] == document["deliveryDocumentId"]
    payload["points"][0].update(isDelivered=False, nonDeliveryReason="Нет доступа")
    assert (await client.post("/protected/delivery-route-sheets/create", json=payload)).status_code == 422


async def test_failed_delivery_migration_preserves_old_rows_and_guards_downgrade(
    client,
    active_employee,
    client_factory,
    postgres,
):
    await API.login(client, active_employee)
    customer = await client_factory()
    response = await create_delivery(
        client,
        json={
            "plannedDate": "2194-05-14",
            "points": [{"clientId": str(customer.client_id), "items": []}],
        },
    )
    assert response.status_code == 201, response.text
    document = response.json()["data"]
    point_id = document["points"][0]["pointId"]
    migration = runpy.run_path(
        str(
            Path(
                "src/common/infra/db/postgres/alembic/migrations/versions/"
                "2026-11-03_18-00_failed_delivery_b917ac56e024/migration.py"
            )
        )
    )

    def migrate(connection, *, upgrade):
        with Operations.context(MigrationContext.configure(connection)):
            migration["upgrade" if upgrade else "downgrade"]()

    async with postgres.session_factory() as session:
        connection = await session.connection()
        await connection.run_sync(migrate, upgrade=False)
        await connection.run_sync(migrate, upgrade=True)
        row = (
            await session.execute(
                text("SELECT is_delivered, non_delivery_reason FROM points WHERE point_id = :id"), {"id": point_id}
            )
        ).one()
        assert row.is_delivered is True
        assert row.non_delivery_reason == ""
        # Roll back the migration exercise, keeping the schema at the current revision.
        await session.rollback()
    path = f"/protected/delivery-route-sheets/{document['deliveryDocumentId']}"
    assert (await client.post(f"{path}/edit-lock")).status_code == 200
    response = await patch_with_revision(
        client,
        path,
        json={
            "points": [
                {
                    "pointId": point_id,
                    "clientId": str(customer.client_id),
                    "items": [],
                    "isDelivered": False,
                    "nonDeliveryReason": "Нет доступа",
                }
            ]
        },
    )
    assert response.status_code == 200, response.text
    async with postgres.session_factory() as session:
        connection = await session.connection()
        with pytest.raises(DBAPIError, match="Restore unsuccessful deliveries"):
            await connection.run_sync(migrate, upgrade=False)
        await session.rollback()
    saved = (await client.get(path)).json()["data"]["points"][0]
    assert saved["pointId"] == point_id
    assert saved["nonDeliveryReason"] == "Нет доступа"
