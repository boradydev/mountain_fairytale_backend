from pathlib import Path
from typing import Any

import pytest
import sqlparse
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from tests.document_requests import create_delivery, patch_with_revision
from tests.helpers import unique_product_name
from tests.integration.api.test_delivery_document_routers import TestDeliveryDocumentRouters as API


PRODUCTS_PATH = "/protected/products"
PICKUP_PATH = "/protected/pickup-sheets"
MIGRATION_DIR = Path(
    "src/common/infra/db/postgres/alembic/migrations/versions/2026-11-03_20-00_free_price_items_4d8b3f7a1c2e"
)


async def _create_free_price_product(client: AsyncClient) -> dict[str, Any]:
    response = await client.post(
        f"{PRODUCTS_PATH}/create",
        json={"name": unique_product_name("free-price"), "basePrice": 125, "isFreePrice": True},
    )
    assert response.status_code == 201, response.text
    product = response.json()["data"]
    assert product["basePrice"] == 0
    assert product["isFreePrice"] is True
    return product


async def test_free_price_catalog_flag_forces_zero_price_and_can_be_disabled(
    client: AsyncClient,
    active_employee,
) -> None:
    await API.login(client, active_employee)
    product = await _create_free_price_product(client)

    response = await client.patch(
        f"{PRODUCTS_PATH}/{product['productId']}",
        json={"isFreePrice": False, "basePrice": 75},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["isFreePrice"] is False
    assert response.json()["data"]["basePrice"] == 75

    response = await client.patch(
        f"{PRODUCTS_PATH}/{product['productId']}",
        json={"isFreePrice": True},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["isFreePrice"] is True
    assert response.json()["data"]["basePrice"] == 0


async def test_route_item_snapshots_free_price_note_and_old_payload_defaults(
    client: AsyncClient,
    active_employee,
    client_factory,
) -> None:
    await API.login(client, active_employee)
    product = await _create_free_price_product(client)
    customer = await client_factory()

    point = API.point_payload(str(customer.client_id), product["productId"], price=0)
    point["items"][0].update(isFreePrice=False)
    mismatched = await create_delivery(client, json={"plannedDate": "2194-06-01", "points": [point]})
    assert mismatched.status_code == 422

    point["items"][0].update(isFreePrice=True, driverNote="  Забрать кулер  ")
    response = await create_delivery(client, json={"plannedDate": "2194-06-01", "points": [point]})
    assert response.status_code == 201, response.text
    document = response.json()["data"]
    path = f"/protected/delivery-route-sheets/{document['deliveryDocumentId']}"
    saved_point = document["points"][0]
    saved_item = saved_point["items"][0]
    assert saved_item["isFreePrice"] is True
    assert saved_item["driverNote"] == "Забрать кулер"

    assert (await client.post(f"{path}/edit-lock")).status_code == 200
    legacy_item_payload = {key: saved_item[key] for key in ("productId", "productName", "quantity", "price")}
    legacy_point_payload = {
        "pointId": saved_point["pointId"],
        "clientId": saved_point["clientId"],
        "items": [legacy_item_payload],
    }
    response = await patch_with_revision(client, path, json={"points": [legacy_point_payload]})
    assert response.status_code == 200, response.text
    preserved = response.json()["data"]["points"][0]["items"][0]
    assert preserved["isFreePrice"] is True
    assert preserved["driverNote"] == "Забрать кулер"

    cleared_note_payload = {
        **legacy_point_payload,
        "items": [{**legacy_item_payload, "isFreePrice": True, "driverNote": ""}],
    }
    response = await patch_with_revision(client, path, json={"points": [cleared_note_payload]})
    assert response.status_code == 200, response.text
    cleared = response.json()["data"]["points"][0]["items"][0]
    assert cleared["isFreePrice"] is True
    assert cleared["driverNote"] == ""

    day = await client.get("/protected/delivery-days/2194-06-01/documents")
    day_document = next(
        entry
        for entry in day.json()["data"]["documents"]
        if entry["deliveryDocumentId"] == document["deliveryDocumentId"]
    )
    day_item = day_document["points"][0]["items"][0]
    assert day_item["isFreePrice"] is True
    assert day_item["driverNote"] == ""

    history = await client.get(
        "/protected/delivery-history",
        params={
            "date_from": "2194-06-01",
            "date_to": "2194-06-01",
            "search": customer.client.name,
        },
    )
    history_item = history.json()["data"]["documents"][0]["matchedClients"][0]["items"][0]
    assert history_item["isFreePrice"] is True
    assert history_item["driverNote"] == ""


async def test_free_price_catalog_products_are_not_available_to_pickup(
    client: AsyncClient,
    active_employee,
) -> None:
    await API.login(client, active_employee)
    product = await _create_free_price_product(client)
    response = await client.post(
        f"{PICKUP_PATH}/create",
        json={
            "plannedDate": "2194-06-02",
            "points": [
                {
                    "items": [
                        {
                            "productId": product["productId"],
                            "productName": product["name"],
                            "quantity": 1,
                            "price": 0,
                            "isFreePrice": False,
                        }
                    ]
                }
            ],
        },
    )
    assert response.status_code == 422, response.text

    response = await client.post(
        f"{PICKUP_PATH}/create",
        json={
            "plannedDate": "2194-06-03",
            "points": [
                {
                    "items": [
                        {
                            "productId": product["productId"],
                            "productName": product["name"],
                            "quantity": 1,
                            "price": 0,
                            "isFreePrice": True,
                        }
                    ]
                }
            ],
        },
    )
    assert response.status_code == 422, response.text


async def test_migration_defaults_old_rows_and_guards_downgrade(postgres) -> None:
    upgrade_sql = (MIGRATION_DIR / "upgrade.sql").read_text(encoding="utf-8")
    downgrade_sql = (MIGRATION_DIR / "downgrade.sql").read_text(encoding="utf-8")

    async with postgres.session_factory() as session:
        connection = await session.connection()

        async def execute_script(sql: str) -> None:
            for statement in sqlparse.split(sql):
                await connection.execute(text(statement))

        await connection.execute(text("CREATE TEMP TABLE products (product_id uuid, base_price numeric NOT NULL)"))
        await connection.execute(text("CREATE TEMP TABLE delivery_document_items (point_id uuid, product_id uuid)"))
        await connection.execute(
            text("INSERT INTO products (product_id, base_price) VALUES ('00000000-0000-0000-0000-000000000001', 0)")
        )
        await connection.execute(
            text(
                "INSERT INTO delivery_document_items (point_id, product_id) "
                "VALUES ('00000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000001')"
            )
        )
        await execute_script(upgrade_sql)

        product = (
            await connection.execute(
                text("SELECT is_free_price FROM products WHERE product_id = '00000000-0000-0000-0000-000000000001'")
            )
        ).one()
        item = (
            await connection.execute(
                text(
                    "SELECT is_free_price, driver_note FROM delivery_document_items "
                    "WHERE point_id = '00000000-0000-0000-0000-000000000002'"
                )
            )
        ).one()
        assert product.is_free_price is False
        assert item.is_free_price is False
        assert item.driver_note == ""

        await connection.execute(
            text("UPDATE products SET is_free_price = true WHERE product_id = '00000000-0000-0000-0000-000000000001'")
        )
        with pytest.raises(DBAPIError, match="Cannot downgrade"):
            await execute_script(downgrade_sql)
        await session.rollback()
