from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import select

from src.common.infra.services.event_pud_service import EventPublisher
from src.feat.commissions.domain.commission_entities import DocumentEmployeeCommission, PointCommission
from tests.helpers import delivery_address, unique_car_number, unique_phone, unique_product_name, unique_username
from tests.integration.api.test_delivery_document_routers import TestDeliveryDocumentRouters as DeliveryAPI


async def create_rep(client, percent="2.5"):
    response = await client.post(
        "/protected/sales-representatives/create",
        json={
            "name": unique_username("rep"),
            "phone": unique_phone(),
            "commissionPercent": percent,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["salesRepresentativeId"]


async def create_customer(client, representative=None):
    response = await client.post(
        "/protected/clients/create",
        json={
            "name": unique_username("client"),
            "phone": unique_phone(),
            "deliveryAddress": delivery_address(),
            "sleepingThresholdDays": 7,
            "salesRepresentativeId": representative,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["clientId"]


async def report(client, month=4, include=False):
    response = await client.get(
        f"/protected/commissions?year=2180&month={month}&include_deactivated={str(include).lower()}"
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def find(rows, key, value):
    return next(row for row in rows if row[key] == value)


@pytest.fixture
async def commission_case(client, admin_employee, active_employee):
    await DeliveryAPI.login(client, admin_employee)
    manager = await client.post(
        "/admin/employees/create",
        json={
            "username": unique_username("commission_manager"),
            "password": "test",
            "commissionPercent": "1.25",
        },
    )
    assert manager.status_code == 201
    manager = manager.json()["data"]["employeeId"]
    await DeliveryAPI.login(client, active_employee)
    rep = await create_rep(client)
    target = await create_rep(client, "7")
    first = await create_customer(client, rep)
    second = await create_customer(client)
    third = await create_customer(client, rep)
    product = await DeliveryAPI.create_product(client, unique_product_name("commission"))

    def point(customer, price="100.10", quantity=1):
        return DeliveryAPI.point_payload(customer, product["productId"], quantity=quantity, price=price)

    response = await client.post(
        "/protected/pickup-sheets/create",
        json={
            "plannedDate": "2180-04-15",
            "points": [point(first), point(second, "50.00")],
        },
    )
    assert response.status_code == 201, response.text
    document = response.json()["data"]
    path = f"/protected/pickup-sheets/{document['deliveryDocumentId']}"
    return dict(
        manager=manager,
        rep=rep,
        target=target,
        first=first,
        second=second,
        third=third,
        point=point,
        document=document,
        path=path,
    )


async def test_historical_snapshots_edit_restore_and_rates(
    client, commission_case, admin_employee, active_employee, postgres
):
    case = commission_case
    async with postgres.session_factory() as session:
        snapshot = await session.get(PointCommission, UUID(case["document"]["points"][0]["pointId"]))
        assert snapshot is not None
        assert snapshot.turnover == Decimal("100.10")
        assert snapshot.commission_payable == Decimal("2.5025")
        assert snapshot.sales_representative_id == UUID(case["rep"])
        employees = (
            await session.scalars(
                select(DocumentEmployeeCommission).where(
                    DocumentEmployeeCommission.delivery_document_id == UUID(case["document"]["deliveryDocumentId"])
                )
            )
        ).all()
        manager = next(entry for entry in employees if str(entry.employee_id) == case["manager"])
        assert manager.commission_payable == Decimal("1.87625")
        assert str(admin_employee.employee_id) not in [str(entry.employee_id) for entry in employees]

    await DeliveryAPI.login(client, admin_employee)
    assert (
        await client.patch(
            f"/admin/employees/{case['manager']}",
            json={
                "commissionPercent": "10",
                "isActive": False,
            },
        )
    ).status_code == 200
    await DeliveryAPI.login(client, active_employee)
    assert (
        await client.patch(
            f"/protected/sales-representatives/{case['rep']}",
            json={
                "commissionPercent": "5",
            },
        )
    ).status_code == 200
    assert (
        await client.patch(
            f"/protected/clients/{case['first']}",
            json={
                "salesRepresentativeId": case["target"],
                "isActive": False,
            },
        )
    ).status_code == 200
    initial = await report(client)
    assert Decimal(
        find(initial["salesRepresentatives"], "salesRepresentativeId", case["rep"])["commissionPayable"]
    ) == Decimal("2.5025")
    historical_manager = find(initial["employees"], "employeeId", case["manager"])
    assert historical_manager["isActive"] is False
    assert Decimal(historical_manager["commissionPayable"]) == Decimal("1.87625")

    assert (await client.post(f"{case['path']}/edit-lock")).status_code == 200
    points = [
        {"pointId": entry["pointId"], "clientId": entry["clientId"], "items": entry["items"]}
        for entry in case["document"]["points"]
    ]
    points[0]["items"][0]["quantity"] = 2
    points.append(case["point"](case["third"], "10"))
    response = await client.patch(case["path"], json={"points": points})
    assert response.status_code == 200, response.text
    changed = await report(client)
    row = find(changed["salesRepresentatives"], "salesRepresentativeId", case["rep"])
    assert Decimal(row["turnover"]) == Decimal("210.20")
    assert Decimal(row["commissionPayable"]) == Decimal("5.505")
    assert [Decimal(rate["commissionPercent"]) for rate in row["commissionRateBreakdown"]] == [
        Decimal("2.5"),
        Decimal("5"),
    ]
    assert Decimal(find(changed["employees"], "employeeId", case["manager"])["commissionPayable"]) == Decimal("3.2525")
    detail = await client.get(f"/protected/commissions/sales-representatives/{case['rep']}?year=2180&month=4")
    first = find(detail.json()["data"]["clients"], "clientId", case["first"])
    assert first["isActive"] is False
    assert first["isCurrentlyAssigned"] is False
    assert Decimal(first["commissionPayable"]) == Decimal("5.005")

    assert (await client.post(f"{case['path']}/cancel")).status_code == 200
    assert Decimal((await report(client))["summary"]["totalTurnover"]) == 0
    assert (await client.post(f"{case['path']}/restore")).status_code == 200
    assert await report(client) == changed
    assert (await client.post(f"{case['path']}/edit-lock")).status_code == 200
    assert (await client.patch(case["path"], json={"plannedDate": "2180-05-01"})).status_code == 200
    assert Decimal((await report(client))["summary"]["totalTurnover"]) == 0
    assert Decimal((await report(client, 5))["summary"]["totalTurnover"]) == Decimal("260.20")
    response = await client.post(
        "/protected/pickup-sheets/create",
        json={
            "plannedDate": "2180-06-01",
            "points": [case["point"](case["third"], "0")],
        },
    )
    assert response.status_code == 201, response.text
    june = await report(client, 6)
    assert case["manager"] not in [employee["employeeId"] for employee in june["employees"]]
    assert find(june["salesRepresentatives"], "salesRepresentativeId", case["rep"])["ordersCount"] == 1


async def test_include_deactivated_employees_preserves_accruals_and_summary(
    client, commission_case, admin_employee, active_employee
):
    case = commission_case
    await DeliveryAPI.login(client, admin_employee)
    response = await client.post(
        "/admin/employees/create",
        json={"username": unique_username("inactive_no_accruals"), "password": "test", "commissionPercent": "0"},
    )
    assert response.status_code == 201, response.text
    employee_id = response.json()["data"]["employeeId"]
    for target_id in (employee_id, case["manager"]):
        response = await client.patch(f"/admin/employees/{target_id}", json={"isActive": False})
        assert response.status_code == 200, response.text
    await DeliveryAPI.login(client, active_employee)

    default = await report(client)
    assert employee_id not in [row["employeeId"] for row in default["employees"]]
    historical = find(default["employees"], "employeeId", case["manager"])
    assert historical["isActive"] is False
    assert Decimal(historical["commissionPayable"]) > 0

    expanded = await report(client, include=True)
    inactive = find(expanded["employees"], "employeeId", employee_id)
    assert inactive["isActive"] is False
    assert Decimal(inactive["turnoverBase"]) == 0
    assert Decimal(inactive["commissionPayable"]) == 0
    assert inactive["commissionRateBreakdown"] == []
    assert find(expanded["employees"], "employeeId", case["manager"]) == historical
    assert str(admin_employee.employee_id) not in [row["employeeId"] for row in expanded["employees"]]
    assert expanded["summary"] == default["summary"]
    assert (await report(client))["employees"] == default["employees"]


async def test_reassign_inactive_clients_source_and_visibility(client, commission_case):
    case = commission_case
    assert (await client.patch(f"/protected/clients/{case['third']}", json={"isActive": False})).status_code == 200
    assert (
        await client.patch(f"/protected/sales-representatives/{case['rep']}", json={"isActive": False})
    ).status_code == 200
    # A fired representative remains accessible even in a month without accruals while clients are assigned.
    assert case["rep"] in [row["salesRepresentativeId"] for row in (await report(client, 12))["salesRepresentatives"]]
    assignment = f"/protected/sales-representatives/{case['rep']}/clients/assignment"
    response = await client.put(assignment, json={"targetSalesRepresentativeId": case["target"]})
    assert response.status_code == 200, response.text
    assert response.json()["data"]["updatedClientsCount"] == 2
    for customer in (case["first"], case["third"]):
        saved = (await client.get(f"/protected/clients/{customer}")).json()["data"]
        assert saved["salesRepresentativeId"] == case["target"]
    assert (await client.get(f"/protected/clients/{case['third']}")).json()["data"]["isActive"] is False
    assert case["rep"] not in [
        row["salesRepresentativeId"] for row in (await report(client, 12))["salesRepresentatives"]
    ]
    assert case["rep"] in [
        row["salesRepresentativeId"] for row in (await report(client, 12, True))["salesRepresentatives"]
    ]
    historical = await report(client)
    assert case["rep"] in [row["salesRepresentativeId"] for row in historical["salesRepresentatives"]]
    assert (await report(client, include=True))["summary"] == historical["summary"]
    # Ordinary authenticated users can transfer; target must be active, and snapshots remain with the original rep.
    target_assignment = f"/protected/sales-representatives/{case['target']}/clients/assignment"
    assert (await client.put(target_assignment, json={"targetSalesRepresentativeId": case["rep"]})).status_code == 409
    assert (
        await client.put(target_assignment, json={"targetSalesRepresentativeId": case["target"]})
    ).status_code == 422
    response = await client.put(target_assignment, json={"targetSalesRepresentativeId": None})
    assert response.status_code == 200
    assert response.json()["data"]["updatedClientsCount"] == 2
    assert (await client.get(f"/protected/clients/{case['third']}")).json()["data"]["salesRepresentativeId"] is None


async def test_commission_validation_and_auth(client, active_employee):
    assert (await client.get("/protected/commissions?year=2180&month=4")).status_code == 401
    await DeliveryAPI.login(client, active_employee)
    for query in ("year=2180&month=0", "year=2180&month=13", "year=10000&month=1", "year=abc&month=1"):
        assert (await client.get(f"/protected/commissions?{query}")).status_code == 422


async def test_deactivated_representative_stops_new_accruals_but_preserves_existing_snapshots(
    client, commission_case, postgres
):
    case = commission_case
    rep_path = f"/protected/sales-representatives/{case['rep']}"
    assert (await client.patch(rep_path, json={"isActive": False})).status_code == 200

    response = await client.post(
        "/protected/pickup-sheets/create",
        json={"plannedDate": "2182-07-01", "points": [case["point"](case["first"])]},
    )
    assert response.status_code == 201, response.text
    created = response.json()["data"]
    point_id = UUID(created["points"][0]["pointId"])
    path = f"/protected/pickup-sheets/{created['deliveryDocumentId']}"
    async with postgres.session_factory() as session:
        snapshot = await session.get(PointCommission, point_id)
        assert snapshot is not None
        assert snapshot.sales_representative_id is None
        assert snapshot.commission_percent == 0
        assert snapshot.commission_payable == 0
        assert snapshot.turnover == Decimal("100.10")

    # The client is still assigned for handover; the inactive rep receives no new turnover or commission.
    customer = (await client.get(f"/protected/clients/{case['first']}")).json()["data"]
    assert customer["salesRepresentativeId"] == case["rep"]
    july_response = await client.get("/protected/commissions?year=2182&month=7")
    assert july_response.status_code == 200
    july = july_response.json()["data"]
    representative = find(july["salesRepresentatives"], "salesRepresentativeId", case["rep"])
    assert representative["isActive"] is False
    assert representative["assignedClientsCount"] == 2
    assert representative["ordersCount"] == 0
    assert Decimal(representative["turnover"]) == 0
    assert Decimal(representative["commissionPayable"]) == 0
    assert Decimal(july["summary"]["unassignedTurnover"]) == Decimal("100.10")
    assert Decimal(find(july["employees"], "employeeId", case["manager"])["commissionPayable"]) == Decimal("1.25125")

    # Editing an old point retains its historical recipient/rate. A new point added now has no recipient.
    assert (await client.post(f"{case['path']}/edit-lock")).status_code == 200
    points = [
        {"pointId": entry["pointId"], "clientId": entry["clientId"], "items": entry["items"]}
        for entry in case["document"]["points"]
    ]
    points[0]["items"][0]["quantity"] = 3
    points.append(case["point"](case["third"], "10"))
    updated_response = await client.patch(case["path"], json={"points": points})
    assert updated_response.status_code == 200, updated_response.text
    updated = updated_response.json()["data"]
    async with postgres.session_factory() as session:
        historical = await session.get(PointCommission, UUID(updated["points"][0]["pointId"]))
        added = await session.get(PointCommission, UUID(updated["points"][2]["pointId"]))
        assert historical.sales_representative_id == UUID(case["rep"])
        assert historical.commission_percent == Decimal("2.5")
        assert historical.commission_payable == Decimal("7.5075")
        assert added.sales_representative_id is None
        assert added.commission_payable == 0
    before_cancel = await report(client)
    assert (await client.post(f"{case['path']}/cancel")).status_code == 200
    assert (await client.post(f"{case['path']}/restore")).status_code == 200
    assert await report(client) == before_cancel

    # Reactivation applies to new points only; editing an earlier unassigned snapshot cannot backfill commission.
    assert (await client.patch(rep_path, json={"isActive": True})).status_code == 200
    assert (await client.post(f"{path}/edit-lock")).status_code == 200
    old_point = created["points"][0]
    response = await client.patch(
        path,
        json={
            "points": [
                {
                    "pointId": old_point["pointId"],
                    "clientId": old_point["clientId"],
                    "items": [{**old_point["items"][0], "quantity": 2}],
                }
            ]
        },
    )
    assert response.status_code == 200, response.text
    async with postgres.session_factory() as session:
        snapshot = await session.get(PointCommission, point_id)
        assert snapshot.sales_representative_id is None
        assert snapshot.commission_payable == 0
        assert snapshot.turnover == Decimal("200.20")
    response = await client.post(
        "/protected/pickup-sheets/create",
        json={"plannedDate": "2182-08-01", "points": [case["point"](case["first"])]},
    )
    assert response.status_code == 201
    august = (await client.get("/protected/commissions?year=2182&month=8")).json()["data"]
    assert Decimal(
        find(august["salesRepresentatives"], "salesRepresentativeId", case["rep"])["commissionPayable"]
    ) == Decimal("2.5025")


async def test_delivery_and_pickup_exact_prices_independent_managers_and_month_boundaries(
    client, admin_employee, active_employee, postgres
):
    await DeliveryAPI.login(client, admin_employee)
    managers = []
    for percent in ("2.5", "3.75"):
        response = await client.post(
            "/admin/employees/create",
            json={
                "username": unique_username("manager"),
                "password": "",
                "commissionPercent": percent,
            },
        )
        assert response.status_code == 201
        managers.append(response.json()["data"]["employeeId"])
    await DeliveryAPI.login(client, active_employee)
    representative = await create_rep(client, "7.5")
    customer = await create_customer(client, representative)
    product = await DeliveryAPI.create_product(client, unique_product_name("exact"), base_price="0.335")
    point = DeliveryAPI.point_payload(customer, product["productId"], quantity=3, price="0.335")
    driver = await DeliveryAPI.create_driver(client, unique_username("driver"))
    car = await client.post("/protected/cars/create", json={"model": "Машина", "number": unique_car_number()})
    assert car.status_code == 201, car.text
    for base, planned in (("pickup-sheets", "2181-01-01"), ("delivery-route-sheets", "2181-01-31")):
        payload = {"plannedDate": planned, "points": [point]}
        if base == "delivery-route-sheets":
            payload.update(driverId=driver["driverId"], carId=car.json()["data"]["carId"], startMileage=0)
        response = await client.post(f"/protected/{base}/create", json=payload)
        assert response.status_code == 201, response.text
    saved = (await client.get("/protected/commissions?year=2181&month=1")).json()["data"]
    assert Decimal(saved["summary"]["totalTurnover"]) == Decimal("2.02")
    rep = find(saved["salesRepresentatives"], "salesRepresentativeId", representative)
    assert rep["ordersCount"] == 2
    assert Decimal(rep["commissionPayable"]) == Decimal("0.1515")
    assert Decimal(find(saved["employees"], "employeeId", managers[0])["commissionPayable"]) == Decimal("0.0505")
    assert Decimal(find(saved["employees"], "employeeId", managers[1])["commissionPayable"]) == Decimal("0.07575")
    assert (
        Decimal(
            (await client.get("/protected/commissions?year=2181&month=2")).json()["data"]["summary"]["totalTurnover"]
        )
        == 0
    )
    async with postgres.session_factory() as session:
        from src.feat.products.domain.product_entities import Product

        item = await session.get(Product, UUID(product["productId"]))
        assert item.base_price == Decimal("0.335")


async def test_snapshot_update_and_transfer_roll_back_with_audit_failure(
    client, commission_case, postgres, monkeypatch
):
    case = commission_case
    previous = await report(client)
    assert (await client.post(f"{case['path']}/edit-lock")).status_code == 200
    points = [
        {"pointId": entry["pointId"], "clientId": entry["clientId"], "items": entry["items"]}
        for entry in case["document"]["points"]
    ]
    points[0]["items"][0]["quantity"] = 77

    async def fail_publish(self, *, events):
        raise RuntimeError("Audit persistence failed")

    with monkeypatch.context() as patch:
        patch.setattr(EventPublisher, "publish_many", fail_publish)
        with pytest.raises(RuntimeError, match="Audit persistence failed"):
            await client.patch(case["path"], json={"points": points})
        with pytest.raises(RuntimeError, match="Audit persistence failed"):
            await client.put(
                f"/protected/sales-representatives/{case['rep']}/clients/assignment",
                json={"targetSalesRepresentativeId": case["target"]},
            )
    assert await report(client) == previous
    assert (await client.get(f"/protected/clients/{case['first']}")).json()["data"]["salesRepresentativeId"] == case[
        "rep"
    ]
    async with postgres.session_factory() as session:
        snapshot = await session.get(PointCommission, UUID(case["document"]["points"][0]["pointId"]))
        assert snapshot.commission_payable == Decimal("2.5025")
    assert (await client.patch(case["path"], json={"points": []})).status_code == 200
    async with postgres.session_factory() as session:
        assert await session.get(PointCommission, UUID(case["document"]["points"][0]["pointId"])) is None
