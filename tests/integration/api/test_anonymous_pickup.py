from pathlib import Path

import pytest
import sqlparse
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from src.core.uuid7 import uuid7
from tests.document_requests import patch_with_revision
from tests.helpers import unique_product_name
from tests.integration.api.test_delivery_document_routers import TestDeliveryDocumentRouters as API


BASE = "/protected/pickup-sheets"
MIGRATION = Path(
    "src/common/infra/db/postgres/alembic/migrations/versions/2026-11-03_12-00_anonymous_pickup_82ac739e051d"
)


async def test_anonymous_purchases_payment_order_and_lifecycle(client, active_employee, postgres):
    await API.login(client, active_employee)
    payments = []
    for _ in range(2):
        response = await client.post("/protected/payment-methods/create", json={"name": f"Pickup {uuid7()}"})
        assert response.status_code == 201, response.text
        payments.append(response.json()["data"]["paymentMethodId"])
    product = await API.create_product(client, unique_product_name("anonymous"))
    first = API.point_payload(None, product["productId"], price=12.5)
    first["paymentMethodId"] = payments[0]
    payload = {
        "creationRequestId": str(uuid7()),
        "plannedDate": "2198-04-16",
        "points": [first, {"items": [], "paymentMethodId": payments[1]}, {"items": []}],
    }
    created = await client.post(f"{BASE}/create", json=payload)
    assert created.status_code == 201, created.text
    document = created.json()["data"]
    path = f"{BASE}/{document['deliveryDocumentId']}"
    assert (await client.post(f"{BASE}/create", json=payload)).json()["data"] == document
    assert [p["clientId"] for p in document["points"]] == [None] * 3
    assert [p["paymentMethodId"] for p in document["points"]] == [*payments, None]
    assert all(p["salesRepresentativeId"] is None for p in document["points"])
    ids = [p["pointId"] for p in document["points"]]
    assert len(set(ids)) == 3
    assert (await client.get(path)).json()["data"] == document
    response = await client.get("/protected/delivery-days/2198-04-16/documents")
    assert response.status_code == 200, response.text
    assert response.json()["data"]["documents"][0]["points"] == document["points"]
    report = await client.get("/protected/sales-report?date_from=2198-04-16&date_to=2198-04-16")
    assert report.status_code == 200, report.text
    assert report.json()["data"]["totalAmount"] == "25.00"
    assert (await client.get("/protected/commissions?year=2198&month=4")).status_code == 200
    async with postgres.session_factory() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT p.client_id, p.payment_method_id, pc.sales_representative_id "
                    "FROM points p JOIN point_commissions pc USING (point_id) "
                    "WHERE p.delivery_document_id = :id ORDER BY p.position"
                ),
                {"id": document["deliveryDocumentId"]},
            )
        ).all()
        assert [row.client_id for row in rows] == [None] * 3
        assert [str(row.payment_method_id) if row.payment_method_id else None for row in rows] == [*payments, None]
        assert all(row.sales_representative_id is None for row in rows)
    assert (await client.post(f"{path}/edit-lock")).status_code == 200
    points = [{"pointId": p["pointId"], "items": p["items"]} for p in document["points"]]
    response = await patch_with_revision(client, path, json={"points": points[::-1]})
    assert response.status_code == 422, response.text
    points[0]["paymentMethodId"] = payments[1]
    response = await patch_with_revision(client, path, json={"points": [points[0], points[2], {"items": []}]})
    assert response.status_code == 200, response.text
    saved = response.json()["data"]
    assert [p["pointId"] for p in saved["points"]][:2] == [ids[0], ids[2]]
    assert saved["points"][0]["paymentMethodId"] == payments[1]
    assert [p["position"] for p in saved["points"]] == [0, 1, 2]
    # Removing paymentMethodId from a PATCH preserves its saved value.
    points = [{"pointId": p["pointId"], "items": p["items"]} for p in saved["points"]]
    assert (await patch_with_revision(client, path, json={"points": points})).json()["data"]["points"][0][
        "paymentMethodId"
    ] == payments[1]
    assert (await client.post(f"{path}/cancel")).json()["data"]["isActive"] is False
    assert (await client.post(f"{path}/restore")).json()["data"]["points"] == saved["points"]


async def test_pickup_rejects_client_and_delivery_requires_client(client, active_employee, client_factory, car_factory):
    await API.login(client, active_employee)
    customer = await client_factory()
    response = await client.post(
        f"{BASE}/create",
        json={"plannedDate": "2026-11-03", "points": [{"clientId": str(customer.client_id), "items": []}]},
    )
    assert response.status_code == 422
    car = await car_factory()
    driver = await API.create_driver(client, f"Driver {uuid7()}")
    response = await client.post(
        "/protected/delivery-route-sheets/create",
        json=API.delivery_payload(driver["driverId"], str(car.car_id), [{"items": []}]),
    )
    assert response.status_code == 422


async def test_migration_detaches_only_pickup_and_preserves_sales(
    client, active_employee, client_factory, car_factory, postgres
):
    await API.login(client, active_employee)
    customer = await client_factory()
    car = await car_factory()
    driver = await API.create_driver(client, f"Driver {uuid7()}")
    product = await API.create_product(client, unique_product_name("migration"))
    payment = await client.post("/protected/payment-methods/create", json={"name": f"Legacy {uuid7()}"})
    assert payment.status_code == 201
    payment_id = payment.json()["data"]["paymentMethodId"]
    response = await client.post(
        "/protected/delivery-route-sheets/create",
        json=API.delivery_payload(
            driver["driverId"], str(car.car_id), [API.point_payload(str(customer.client_id), product["productId"])]
        ),
    )
    assert response.status_code == 201, response.text
    delivery_id = response.json()["data"]["deliveryDocumentId"]
    # Emulate a pre-upgrade, cancelled pickup inside a rollback-only transaction.
    async with postgres.session_factory() as session:
        pickup_id, point_id = uuid7(), uuid7()
        await session.execute(
            text(
                "INSERT INTO delivery_documents "
                "(delivery_document_id, document_type, created_at, planned_date, is_active, revision) "
                "VALUES (:id, 'pickup_sheet', now(), '2026-11-03', false, 1)"
            ),
            {"id": pickup_id},
        )
        await session.execute(
            text(
                "INSERT INTO points (point_id, delivery_document_id, client_id, payment_method_id, position) "
                "VALUES (:id, :doc, :client, :payment, 0)"
            ),
            {"id": point_id, "doc": pickup_id, "client": customer.client_id, "payment": payment_id},
        )
        await session.execute(
            text(
                "INSERT INTO delivery_document_items (point_id, product_id, product_name, quantity, price) "
                "VALUES (:id, :product, 'Historical', 3, 15.25)"
            ),
            {"id": point_id, "product": product["productId"]},
        )
        await session.execute(
            text(
                "INSERT INTO point_commissions (point_id, commission_percent, turnover, commission_payable) "
                "VALUES (:id, 5, 45.75, 2.29)"
            ),
            {"id": point_id},
        )
        for statement in sqlparse.split(MIGRATION.joinpath("upgrade.sql").read_text(encoding="utf-8")):
            await session.execute(text(statement))
        row = (
            await session.execute(
                text(
                    "SELECT p.client_id, p.payment_method_id, p.position, "
                    "i.product_name, i.quantity, i.price, pc.commission_payable "
                    "FROM points p JOIN delivery_document_items i USING (point_id) "
                    "JOIN point_commissions pc USING (point_id) "
                    "WHERE p.point_id = :id"
                ),
                {"id": point_id},
            )
        ).one()
        assert row.client_id is None
        assert str(row.payment_method_id) == payment_id
        assert (row.position, row.product_name, row.quantity, str(row.price), row.commission_payable) == (
            0,
            "Historical",
            3,
            "15.25",
            0,
        )
        assert (
            await session.scalar(
                text("SELECT client_id FROM points WHERE delivery_document_id = :id"), {"id": delivery_id}
            )
        ) == customer.client_id
        assert (
            await session.scalar(text("SELECT count(*) FROM clients WHERE client_id = :id"), {"id": customer.client_id})
        ) == 1
        async def downgrade():
            async with session.begin_nested():
                for statement in sqlparse.split(MIGRATION.joinpath("downgrade.sql").read_text(encoding="utf-8")):
                    await session.execute(text(statement))

        with pytest.raises(DBAPIError, match="Cannot restore required client_id"):
            await downgrade()
        assert (await session.scalar(text("SELECT count(*) FROM points WHERE point_id = :id"), {"id": point_id})) == 1
        await session.rollback()
