from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import select

from src.feat.commissions.domain.commission_entities import DocumentEmployeeCommission
from src.feat.employees.domain.employee_entities import Employee
from tests.helpers import unique_product_name, unique_username
from tests.integration.api.test_commissions import create_customer
from tests.integration.api.test_delivery_document_routers import TestDeliveryDocumentRouters as DeliveryAPI


@pytest.mark.parametrize("percent", [None, 0, 100])
async def test_create_optional_rate_is_persisted(client, admin_employee, percent):
    await DeliveryAPI.login(client, admin_employee)
    response = await client.post(
        "/admin/employees/create",
        json={"username": unique_username("optional_rate"), "password": "test", "commissionPercent": percent},
    )
    assert response.status_code == 201
    employee = response.json()["data"]
    assert employee["commissionPercent"] == percent
    saved = await client.get(f"/admin/employees/{employee['employeeId']}")
    assert saved.status_code == 200
    assert saved.json()["data"]["commissionPercent"] == percent


@pytest.mark.parametrize("role", ["admin", "employee"])
async def test_patch_rate_distinguishes_omitted_null_and_zero(client, admin_employee, employee_factory, role):
    target = await employee_factory(role=role, commission_percent=5)
    await DeliveryAPI.login(client, admin_employee)
    path = f"/admin/employees/{target.employee_id}"
    response = await client.patch(path, json={"username": unique_username("renamed_rate")})
    assert response.status_code == 200
    assert response.json()["data"]["commissionPercent"] == 5
    for percent in (None, 0, 2, None):
        response = await client.patch(path, json={"commissionPercent": percent})
        assert response.status_code == 200
        assert response.json()["data"]["commissionPercent"] == percent
        saved = await client.get(path)
        assert saved.status_code == 200
        assert saved.json()["data"]["commissionPercent"] == percent
    for field in ("username", "isActive"):
        assert (await client.patch(path, json={field: None})).status_code == 422
    if role == "admin":
        assert (await client.patch(path, json={"isActive": False})).status_code == 403


async def test_report_and_snapshots_follow_rate_not_role(client, admin_employee, employee_factory, postgres):
    await DeliveryAPI.login(client, admin_employee)
    subjects = []
    for role in ("admin", "employee"):
        for active in (True, False):
            for percent in (None, 0, 2):
                target = await employee_factory(role=role, is_active=active, commission_percent=percent)
                subjects.append((str(target.employee_id), active, percent, role))

    async def rows(month=1, include=False):
        response = await client.get(
            f"/protected/commissions?year=2190&month={month}&include_deactivated={str(include).lower()}"
        )
        assert response.status_code == 200
        return {row["employeeId"]: row for row in response.json()["data"]["employees"]}

    # Without sales, only accounts with a rate appear. The toggle adds inactive accounts with a rate.
    for include in (False, True):
        current = await rows(include=include)
        for target_id, active, percent, _ in subjects:
            assert (target_id in current) == (percent is not None and (active or include))
            if target_id in current:
                assert Decimal(current[target_id]["turnoverBase"]) == 0
                assert Decimal(current[target_id]["commissionPayable"]) == 0
                assert current[target_id]["commissionRateBreakdown"] == []

    customer = await create_customer(client)
    product = await DeliveryAPI.create_product(client, unique_product_name("optional_rate"))
    point = DeliveryAPI.point_payload(customer, product["productId"], quantity=1, price="100")
    created = await client.post(
        "/protected/pickup-sheets/create", json={"plannedDate": "2190-01-05", "points": [point]}
    )
    assert created.status_code == 201
    document = created.json()["data"]
    document_id = UUID(document["deliveryDocumentId"])
    path = f"/protected/pickup-sheets/{document_id}"
    async with postgres.session_factory() as session:
        snapshots = {
            str(entry.employee_id): entry
            for entry in (
                await session.scalars(
                    select(DocumentEmployeeCommission).where(
                        DocumentEmployeeCommission.delivery_document_id == document_id
                    )
                )
            ).all()
        }
        for target_id, active, percent, _ in subjects:
            assert (target_id in snapshots) == (active and percent is not None)
            if target_id in snapshots:
                assert snapshots[target_id].turnover == Decimal("100")
                assert snapshots[target_id].commission_percent == Decimal(percent)
                assert snapshots[target_id].commission_payable == Decimal(percent)

    historical_ids = {target_id for target_id, active, percent, _ in subjects if active and percent is not None}
    # Clear both positive and zero rates for both roles. Employee deactivation cannot hide history either.
    for target_id, _active, _percent, role in subjects:
        if target_id not in historical_ids:
            continue
        payload = {"commissionPercent": None}
        if role == "employee":
            payload["isActive"] = False
        response = await client.patch(f"/admin/employees/{target_id}", json=payload)
        assert response.status_code == 200
        saved = await client.get(f"/admin/employees/{target_id}")
        assert saved.json()["data"]["commissionPercent"] is None
    for include in (False, True):
        current = await rows(include=include)
        for target_id in historical_ids:
            assert Decimal(current[target_id]["turnoverBase"]) == 100
        assert historical_ids.isdisjoint(await rows(month=2, include=include))

    # New documents omit those recipients; editing an old document retains and recalculates its old rates.
    created = await client.post(
        "/protected/pickup-sheets/create", json={"plannedDate": "2190-02-05", "points": [point]}
    )
    assert created.status_code == 201
    assert historical_ids.isdisjoint(await rows(month=2, include=True))
    assert (await client.post(f"{path}/edit-lock")).status_code == 200
    old_point = document["points"][0]
    old_point["items"][0]["quantity"] = 2
    response = await client.patch(
        path, json={"points": [{"pointId": old_point["pointId"], **point, "items": old_point["items"]}]}
    )
    assert response.status_code == 200
    current = await rows()
    for target_id, _, percent, _ in subjects:
        if target_id in historical_ids:
            assert Decimal(current[target_id]["turnoverBase"]) == 200
            assert Decimal(current[target_id]["commissionPayable"]) == Decimal(percent) * 2
            assert Decimal(current[target_id]["commissionRateBreakdown"][0]["commissionPercent"]) == percent
    assert (await client.post(f"{path}/cancel")).status_code == 200
    assert historical_ids.isdisjoint(await rows(include=True))
    assert (await client.post(f"{path}/restore")).status_code == 200
    restored = await rows()
    for target_id in historical_ids:
        assert restored[target_id] == current[target_id]


async def test_assigning_rate_never_backfills_document_with_empty_snapshots(
    client, admin_employee, employee_factory, postgres
):
    await DeliveryAPI.login(client, admin_employee)
    target = await employee_factory(commission_percent=None)
    customer = await create_customer(client)
    product = await DeliveryAPI.create_product(client, unique_product_name("empty_snapshots"))
    point = DeliveryAPI.point_payload(customer, product["productId"], quantity=1, price="100")
    # Isolate a genuinely empty recipient list, regardless of accounts from earlier tests.
    async with postgres.session_factory() as session:
        existing = (await session.scalars(select(Employee).where(Employee.commission_percent.is_not(None)))).all()
        previous_rates = {employee.employee_id: employee.commission_percent for employee in existing}
        for employee in existing:
            employee.commission_percent = None
        await session.commit()
    try:
        async with postgres.session_factory() as session:
            assert not (await session.scalars(select(Employee).where(Employee.commission_percent.is_not(None)))).all()
        response = await client.post(
            "/protected/pickup-sheets/create", json={"plannedDate": "2191-01-05", "points": [point]}
        )
        assert response.status_code == 201
        document = response.json()["data"]
        document_id = UUID(document["deliveryDocumentId"])
        path = f"/protected/pickup-sheets/{document_id}"
        async with postgres.session_factory() as session:
            assert not (
                await session.scalars(
                    select(DocumentEmployeeCommission).where(
                        DocumentEmployeeCommission.delivery_document_id == document_id
                    )
                )
            ).all()
        response = await client.patch(f"/admin/employees/{target.employee_id}", json={"commissionPercent": 2})
        assert response.status_code == 200
        saved = await client.get(f"/admin/employees/{target.employee_id}")
        assert saved.json()["data"]["commissionPercent"] == 2
        assert (await client.post(f"{path}/edit-lock")).status_code == 200
        assert (await client.patch(path, json={"plannedDate": "2191-02-01"})).status_code == 200
        assert (await client.post(f"{path}/cancel")).status_code == 200
        assert (await client.post(f"{path}/restore")).status_code == 200
        async with postgres.session_factory() as session:
            assert not (
                await session.scalars(
                    select(DocumentEmployeeCommission).where(
                        DocumentEmployeeCommission.delivery_document_id == document_id
                    )
                )
            ).all()
        new_document = await client.post(
            "/protected/pickup-sheets/create", json={"plannedDate": "2191-02-05", "points": [point]}
        )
        assert new_document.status_code == 201
        async with postgres.session_factory() as session:
            snapshot = await session.get(
                DocumentEmployeeCommission,
                (UUID(new_document.json()["data"]["deliveryDocumentId"]), target.employee_id),
            )
            assert snapshot is not None
            assert snapshot.commission_percent == Decimal(2)
            assert snapshot.commission_payable == Decimal(2)
    finally:
        async with postgres.session_factory() as session:
            for employee_id, rate in previous_rates.items():
                employee = await session.get(Employee, employee_id)
                employee.commission_percent = rate
            await session.commit()
