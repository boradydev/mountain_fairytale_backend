from datetime import date, datetime, timedelta
from uuid import uuid4

from tests.document_requests import create_delivery
from tests.helpers import delivery_address, unique_phone, unique_product_name
from tests.integration.api.test_delivery_document_routers import TestDeliveryDocumentRouters as DeliveryAPI


async def customer(client, name, threshold=10, **extra):
    response = await client.post(
        "/protected/clients/create",
        json={
            "name": name,
            "phone": unique_phone(),
            "deliveryAddress": delivery_address(),
            "sleepingThresholdDays": threshold,
            **extra,
        },
    )
    assert response.status_code == 201, response.text
    row = response.json()["data"]
    read = await client.get(f"/protected/clients/{row['clientId']}")
    assert read.json()["data"] == row
    return row


async def listing(client, **params):
    response = await client.get("/protected/clients", params={"limit": 25, **params})
    assert response.status_code == 200, response.text
    return response.json()


async def test_follow_up_pagination_ties_cooldown_and_default_mode(client, active_employee):
    await DeliveryAPI.login(client, active_employee)
    prefix = f"pages-{uuid4()}"
    rows = [await customer(client, prefix) for _ in range(53)]
    cooldown = await customer(client, prefix, cooldownUntil=(datetime.now() + timedelta(days=1)).isoformat())
    inactive = await customer(client, prefix)
    response = await client.patch(f"/protected/clients/{inactive['clientId']}", json={"isActive": False})
    assert response.status_code == 200
    database = await listing(client, search=prefix, limit=100, include_deactivated=True)
    explicit = await listing(client, search=prefix, limit=100, include_deactivated=True, mode="database")
    assert database == explicit
    assert database["total"] == 55
    assert [r["clientId"] for r in database["data"]["clients"]] == [
        r["clientId"]
        for r in sorted([*rows, cooldown, inactive], key=lambda r: (r["createdAt"], r["clientId"]), reverse=True)
    ]
    database_ids = []
    for offset, size in [(0, 25), (25, 25), (50, 4)]:
        page = await listing(client, search=prefix, offset=offset)
        assert page["total"] == 54
        assert len(page["data"]["clients"]) == size
        database_ids.extend(row["clientId"] for row in page["data"]["clients"])
    assert database_ids == [
        row["clientId"] for row in database["data"]["clients"] if row["clientId"] != inactive["clientId"]
    ]
    ids = []
    for offset, size in [(0, 25), (25, 25), (50, 3), (75, 0)]:
        page = await listing(client, search=prefix, mode="follow_up", offset=offset, include_deactivated=True)
        assert page["total"] == 53
        assert len(page["data"]["clients"]) == size
        ids.extend(r["clientId"] for r in page["data"]["clients"])
    assert ids == sorted(r["clientId"] for r in rows)
    invalid = await client.get("/protected/clients", params={"mode": "other"})
    assert invalid.status_code == 422


async def test_follow_up_order_boundaries_and_successful_sales(client, active_employee):
    await DeliveryAPI.login(client, active_employee)
    prefix = f"urgency-{uuid4()}"
    specs = [
        ("never", 10, None),
        ("zero", 0, 0),
        ("urgent", 10, 30),
        ("equal-a", 10, 20),
        ("equal-b", 5, 10),
        ("boundary", 10, 10),
        ("normal", 10, 9),
        ("future", 10, -1),
        ("cancelled", 10, 0),
        ("undelivered", 10, 0),
        ("empty", 10, None),
        ("expired", 10, None),
    ]
    rows = {}
    product = await DeliveryAPI.create_product(client, unique_product_name("follow_up"))
    for suffix, threshold, days in specs:
        extra = {"cooldownUntil": (datetime.now() - timedelta(seconds=1)).isoformat()} if suffix == "expired" else {}
        row = await customer(client, f"{prefix} {suffix}", threshold, **extra)
        rows[suffix] = row
        if days is None and suffix != "empty":
            continue
        point = DeliveryAPI.point_payload(row["clientId"], product["productId"])
        if suffix == "undelivered":
            point.update(isDelivered=False, nonDeliveryReason="Закрыто")
        if suffix == "empty":
            point["items"] = []
        response = await create_delivery(
            client,
            json={
                "plannedDate": (date.today() - timedelta(days=days or 0)).isoformat(),
                "points": [point],
            },
        )
        assert response.status_code == 201, response.text
        if suffix == "cancelled":
            response = await client.post(
                f"/protected/delivery-route-sheets/{response.json()['data']['deliveryDocumentId']}/cancel"
            )
            assert response.status_code == 200, response.text
    page = await listing(client, mode="follow_up", search=prefix)
    expected = [
        "cancelled",
        "empty",
        "expired",
        "never",
        "undelivered",
        "zero",
        "urgent",
        "equal-a",
        "equal-b",
        "boundary",
    ]
    assert page["total"] == len(expected)
    assert [r["clientId"] for r in page["data"]["clients"]] == [rows[key]["clientId"] for key in expected]
    assert (await listing(client, mode="follow_up", search=rows["normal"]["phone"]))["total"] == 0
    for key in ["cancelled", "undelivered", "empty"]:
        assert next(r for r in page["data"]["clients"] if r["clientId"] == rows[key]["clientId"])["lastOrder"] is None


async def test_client_search_literal_details_phone_and_total(client, active_employee):
    await DeliveryAPI.login(client, active_employee)
    marker = str(uuid4())
    row = await customer(
        client, f"ИВАНОВ {marker}", phone=str(uuid4().int)[-20:], deliveryDetails=f"Подъезд %_\\ {marker}"
    )
    for query in [f"иванов {marker}", f"%_\\ {marker}", row["address"], row["phone"][3:]]:
        page = await listing(client, search=query)
        assert row["clientId"] in [r["clientId"] for r in page["data"]["clients"]]
    literal = await listing(client, search=f"%_\\ {marker}")
    assert literal["total"] == 1
    empty = await listing(client, search=f"%_\\ {marker}", offset=25)
    assert empty["total"] == 1
    assert empty["data"]["clients"] == []
    too_long = await client.get("/protected/clients", params={"search": "a" * 501})
    assert too_long.status_code == 422
