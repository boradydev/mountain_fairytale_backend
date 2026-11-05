from pathlib import Path
from uuid import UUID

import sqlparse
from sqlalchemy import text

from tests.document_requests import create_delivery, patch_with_revision
from tests.helpers import unique_product_name
from tests.integration.api.test_delivery_document_contract import read_events
from tests.integration.api.test_delivery_document_routers import TestDeliveryDocumentRouters as API


async def test_snapshots_search_points_and_document_filter(client, active_employee, client_factory, postgres):
    await API.login(client, active_employee)
    customer = await client_factory(name=r"Old %_\ name", address="First historical address", phone="+7 999 101 22 33")
    other = await client_factory(name="Another customer")
    product = await API.create_product(client, unique_product_name("snapshot"))
    params = {"date_from": "2391-04-01", "date_to": "2391-04-30"}

    async def create(day, points):
        response = await create_delivery(client, json={"plannedDate": day, "points": points})
        assert response.status_code == 201, response.text
        return response.json()["data"]

    first = await create(
        "2391-04-01",
        [
            API.point_payload(str(customer.client_id), product["productId"], price="1.005"),
            {
                **API.point_payload(str(other.client_id), product["productId"], price=20),
                "isDelivered": False,
                "nonDeliveryReason": "Absent",
            },
        ],
    )
    async with postgres.session_factory() as session:
        await session.execute(
            text(
                "UPDATE clients SET name = 'Current vector', address = 'Second address', "
                "phone = '+7 999 404 55 66', delivery_details = 'Current details' WHERE client_id = :id"
            ),
            {"id": customer.client_id},
        )
        await session.commit()
    second = await create("2391-04-02", [API.point_payload(str(customer.client_id), product["productId"])])
    async with postgres.session_factory() as session:
        await session.execute(
            text("UPDATE clients SET is_active = false WHERE client_id = :id"), {"id": customer.client_id}
        )
        await session.commit()

    async def history(search="", **extra):
        response = await client.get("/protected/client-delivery-history", params={**params, "search": search, **extra})
        assert response.status_code == 200, response.text
        return response.json()

    result = await history("Current vector")
    assert result["total"] == 2
    assert [p["clientName"] for p in result["data"]["deliveries"]] == ["Current vector", r"Old %_\ name"]
    for term in ["First historical", "9991012233", r"%_\ name"]:
        result = await history(term)
        assert result["total"] == 1
        assert result["data"]["deliveries"][0]["pointId"] == first["points"][0]["pointId"]
    assert (await history("Current details"))["total"] == 2
    result = await history()
    assert result["total"] == 3
    failed = next(p for p in result["data"]["deliveries"] if not p["isDelivered"])
    assert failed["nonDeliveryReason"] == "Absent"
    assert failed["totalAmount"] == "40.00"
    assert failed["documentTotalAmount"] == "2.01"
    assert (await history(offset=100))["total"] == 3
    assert (await history(offset=100))["data"]["deliveries"] == []
    page = await history(limit=1)
    next_page = await history(limit=1, offset=1)
    assert page["data"]["deliveries"][0]["pointId"] != next_page["data"]["deliveries"][0]["pointId"]
    loaded = (await client.get(f"/protected/delivery-route-sheets/{first['deliveryDocumentId']}")).json()["data"]
    assert loaded["points"][0]["clientName"] == r"Old %_\ name"
    assert loaded["points"][0]["clientAddress"] == "First historical address"
    await client.post("/protected/pickup-sheets/create", json={"plannedDate": "2391-04-03", "points": [{"items": []}]})
    docs = await client.get("/protected/delivery-history", params=params)
    assert docs.json()["total"] == 3
    docs = await client.get("/protected/delivery-history", params={**params, "document_type": "pickup_sheet"})
    assert docs.json()["total"] == 1
    assert (await history())["total"] == 3
    await client.post(f"/protected/delivery-route-sheets/{second['deliveryDocumentId']}/cancel")
    assert (await history())["total"] == 2


async def test_new_point_captures_rep_but_existing_snapshot_and_commission_stay(
    client, active_employee, client_factory, postgres
):
    await API.login(client, active_employee)
    rep = (
        await client.post(
            "/protected/sales-representatives/create",
            json={
                "name": "Snapshot representative",
                "phone": "+79991112288",
                "commissionPercent": "7.5",
            },
        )
    ).json()["data"]
    customer = await client_factory(name="Saved customer")
    new_customer = await client_factory(name="New point customer")
    product = await API.create_product(client, unique_product_name("rep-snapshot"))
    response = await create_delivery(
        client,
        json={
            "plannedDate": "2188-05-01",
            "points": [API.point_payload(str(customer.client_id), product["productId"])],
        },
    )
    assert response.status_code == 201, response.text
    doc = response.json()["data"]
    async with postgres.session_factory() as session:
        before = (
            (
                await session.execute(
                    text("SELECT * FROM point_commissions WHERE point_id = :id"),
                    {"id": UUID(doc["points"][0]["pointId"])},
                )
            )
            .mappings()
            .one()
        )
        await session.execute(
            text("UPDATE clients SET name = 'Changed', sales_representative_id = :rep WHERE client_id IN (:a, :b)"),
            {"rep": UUID(rep["salesRepresentativeId"]), "a": customer.client_id, "b": new_customer.client_id},
        )
        await session.commit()
    doc_id = doc["deliveryDocumentId"]
    assert (await client.post(f"/protected/delivery-route-sheets/{doc_id}/edit-lock")).status_code == 200
    original = doc["points"][0]
    response = await patch_with_revision(
        client,
        f"/protected/delivery-route-sheets/{doc_id}",
        json={
            "points": [
                {"pointId": original["pointId"], "clientId": original["clientId"], "items": original["items"]},
                API.point_payload(str(new_customer.client_id), product["productId"]),
            ]
        },
    )
    assert response.status_code == 200, response.text
    points = response.json()["data"]["points"]
    assert points[0]["clientName"] == "Saved customer"
    assert points[0]["salesRepresentativeId"] is None
    assert points[1]["salesRepresentativeId"] == rep["salesRepresentativeId"]
    async with postgres.session_factory() as session:
        after = (
            (
                await session.execute(
                    text("SELECT * FROM point_commissions WHERE point_id = :id"), {"id": UUID(original["pointId"])}
                )
            )
            .mappings()
            .one()
        )
        assert dict(before) == dict(after)
        await session.execute(
            text(
                "UPDATE sales_representatives SET name = 'Renamed inactive representative', is_active = false "
                "WHERE sales_representative_id = :id"
            ),
            {"id": UUID(rep["salesRepresentativeId"])},
        )
        await session.execute(
            text("UPDATE clients SET sales_representative_id = NULL WHERE client_id = :id"),
            {"id": new_customer.client_id},
        )
        await session.commit()
    loaded = (await client.get(f"/protected/delivery-route-sheets/{doc_id}")).json()["data"]
    assert loaded["points"][1]["salesRepresentativeId"] == rep["salesRepresentativeId"]
    assert loaded["points"][1]["salesRepresentativeName"] == "Renamed inactive representative"
    events = await read_events(postgres, loaded)
    creation = next(event for event in events if event["event_type"] == "CreateDeliveryDocumentEvent")
    assert creation["payload"]["data"]["points"][0]["snapshot_client_name"] == "Saved customer"


async def test_client_snapshot_migration_backfills_and_roundtrips(postgres):
    folder = Path(
        "src/common/infra/db/postgres/alembic/migrations/versions/2026-11-04_12-00_client_snapshots_1e8c3a5d907b"
    )
    async with postgres.session_factory() as session:
        # Temp tables shadow real relations; no deployed data or commissions are modified.
        await session.execute(
            text("CREATE TEMP TABLE sales_representatives (sales_representative_id uuid PRIMARY KEY) ON COMMIT DROP")
        )
        await session.execute(
            text(
                "CREATE TEMP TABLE clients (client_id uuid, name text, phone text, address text, "
                "delivery_details text, sales_representative_id uuid) ON COMMIT DROP"
            )
        )
        await session.execute(text("CREATE TEMP TABLE points (point_id uuid, client_id uuid) ON COMMIT DROP"))
        await session.execute(text("INSERT INTO sales_representatives VALUES (:id)"), {"id": UUID(int=3)})
        await session.execute(
            text("INSERT INTO clients VALUES (:id, 'Current', '123', 'Address', '', :rep)"),
            {"id": UUID(int=1), "rep": UUID(int=3)},
        )
        await session.execute(
            text("INSERT INTO points VALUES (:p, :c), (:anonymous, NULL)"),
            {"p": UUID(int=2), "c": UUID(int=1), "anonymous": UUID(int=4)},
        )
        for filename in ["upgrade.sql", "downgrade.sql", "upgrade.sql"]:
            for statement in sqlparse.split((folder / filename).read_text(encoding="utf-8")):
                await session.execute(text(statement))
        rows = (await session.execute(text("SELECT * FROM points ORDER BY point_id"))).mappings().all()
        assert rows[0]["snapshot_client_name"] == "Current"
        assert rows[0]["snapshot_sales_representative_id"] == UUID(int=3)
        assert rows[1]["snapshot_client_name"] is None
        assert rows[1]["snapshot_sales_representative_id"] is None
        await session.rollback()


async def test_client_history_validation_and_auth(client):
    assert (
        await client.get(
            "/protected/client-delivery-history", params={"date_from": "2026-01-01", "date_to": "2026-01-02"}
        )
    ).status_code == 401
