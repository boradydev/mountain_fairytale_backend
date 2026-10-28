"""Monthly employee turnover counts eligible documents, not recipient rows."""

from decimal import Decimal

from sqlalchemy import select, update

from src.feat.employees.domain.employee_entities import Employee
from tests.document_requests import patch_with_revision
from tests.helpers import unique_car_number, unique_product_name
from tests.integration.api.test_commissions import create_customer
from tests.integration.api.test_delivery_document_routers import TestDeliveryDocumentRouters as DeliveryAPI


async def test_employee_turnover_uses_unique_historical_documents(client, admin_employee, employee_factory, postgres):
    await DeliveryAPI.login(client, admin_employee)
    async with postgres.session_factory() as session:
        existing = (await session.scalars(select(Employee))).all()
        original_rates = {e.employee_id: e.commission_percent for e in existing}
        await session.execute(update(Employee).values(commission_percent=None))
        await session.commit()
    first = await employee_factory(commission_percent=None)
    second = await employee_factory(role="admin", commission_percent=None)
    customer = await create_customer(client)
    product = await DeliveryAPI.create_product(client, unique_product_name("employee_turnover"))

    async def set_rate(employee, value, **extra):
        response = await client.patch(
            f"/admin/employees/{employee.employee_id}", json={"commissionPercent": value, **extra}
        )
        assert response.status_code == 200, response.text

    async def create(amount, *, delivery=False):
        payload = {
            "plannedDate": "2194-01-10",
            "points": [DeliveryAPI.point_payload(customer, product["productId"], quantity=1, price=amount)],
        }
        base = "/protected/pickup-sheets"
        if delivery:
            driver = await DeliveryAPI.create_driver(client, "Turnover driver")
            car = await client.post(
                "/protected/cars/create", json={"model": "Turnover car", "number": unique_car_number()}
            )
            assert car.status_code == 201
            payload.update(driverId=driver["driverId"], carId=car.json()["data"]["carId"], startMileage=0)
            base = "/protected/delivery-route-sheets"
        response = await client.post(f"{base}/create", json=payload)
        assert response.status_code == 201, response.text
        doc = response.json()["data"]
        return f"{base}/{doc['deliveryDocumentId']}", doc

    async def summary(expected, *, total=None, month=1):
        values = []
        for include in (False, True):
            response = await client.get(
                f"/protected/commissions?year=2194&month={month}&include_deactivated={str(include).lower()}"
            )
            assert response.status_code == 200, response.text
            body = response.json()["data"]["summary"]
            assert Decimal(body["employeeTurnover"]) == Decimal(expected)
            if total is not None:
                assert Decimal(body["totalTurnover"]) == Decimal(total)
            values.append(body)
        assert values[0] == values[1]

    try:
        old_path, old = await create("700")
        await summary("0", total="700")
        await set_rate(first, 2)
        await set_rate(second, 0)
        pickup_path, _ = await create("700")
        delivery_path, _ = await create("300", delivery=True)
        # Two recipients per document still produce 1000, not 2000.
        await summary("1000", total="1700")
        await set_rate(first, None, isActive=False)
        await set_rate(second, None)
        await create("200")
        await summary("1000", total="1900")
        # Assigning a rate and editing an older document cannot backfill recipients.
        await set_rate(second, 4)
        assert (await client.post(f"{old_path}/edit-lock")).status_code == 200
        point = old["points"][0]
        point["items"][0]["quantity"] = 2
        response = await patch_with_revision(
            client,
            old_path,
            json={"points": [{"pointId": point["pointId"], "clientId": point["clientId"], "items": point["items"]}]},
        )
        assert response.status_code == 200
        await summary("1000", total="2600")
        assert (await client.post(f"{pickup_path}/cancel")).status_code == 200
        await summary("300", total="1900")
        assert (await client.post(f"{pickup_path}/restore")).status_code == 200
        await summary("1000", total="2600")
        assert (await client.post(f"{delivery_path}/edit-lock")).status_code == 200
        response = await patch_with_revision(client, delivery_path, json={"plannedDate": "2194-02-01"})
        assert response.status_code == 200
        await summary("700", total="2300")
        await summary("300", total="300", month=2)
        # Explicit zero rate alone counts; an absent rate above did not.
        await set_rate(second, 0)
        await create("90")
        await summary("790", total="2390")
        # Equal amounts in different eligible documents must not collapse.
        await create("700")
        await summary("1490", total="3090")
        await summary("0", total="0", month=3)
    finally:
        async with postgres.session_factory() as session:
            for employee_id, value in original_rates.items():
                await session.execute(
                    update(Employee).where(Employee.employee_id == employee_id).values(commission_percent=value)
                )
            for target in (first, second):
                await session.execute(
                    update(Employee).where(Employee.employee_id == target.employee_id).values(commission_percent=None)
                )
            await session.commit()
