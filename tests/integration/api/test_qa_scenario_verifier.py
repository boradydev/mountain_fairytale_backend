"""Verify real API/SQL contracts only in the suite's disposable *_test database."""

import copy
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest

from scripts.qa.scenarios import Checks, Runner, clean, expected_plan, finances, snapshot, verify_document
from src.common.infra.db.postgres.settings import PostgresSettings
from tests.document_requests import patch_with_revision
from tests.helpers import unique_phone, unique_product_name
from tests.integration.api.test_delivery_document_routers import TestDeliveryDocumentRouters as API
from tests.integration.db_helpers import validate_test_database_name


@pytest.mark.parametrize("pickup", [False, True])
async def test_real_scenario_lifecycle_verification(
    client, active_employee, employee_factory, car_factory, test_database_name, pickup
):
    validate_test_database_name(test_database_name)
    await API.login(client, active_employee)
    await employee_factory(commission_percent=1.25)
    cards, objects = {}, {}

    async def create(key, resource, body):
        response = await client.post(f"/protected/{resource}/create", json=body)
        assert response.status_code == 201, response.text
        cards[key] = response.json()["data"]
        id_key = next(k for k in cards[key] if k.endswith("Id") and cards[key][k] is not None)
        objects[key] = dict(id=cards[key][id_key])

    for i, name in enumerate(["Наличные", "Карта", "Перевод"]):
        await create(f"payment{i}", "payment-methods", dict(name=f"QA adapter {name} {uuid4()}"))
    for i, rate in [(0, "7.5"), (1, "0")]:
        await create(
            f"rep{i}",
            "sales-representatives",
            dict(name=f"QA rep {uuid4()}", phone=unique_phone(), commissionPercent=rate),
        )
        await create(
            f"client{21 + i}",
            "clients",
            dict(
                name=f"QA client {uuid4()}",
                phone=unique_phone(),
                address="QA address",
                sleepingThresholdDays=30,
                salesRepresentativeId=objects[f"rep{i}"]["id"],
                defaultPaymentMethodId=objects[f"payment{i}"]["id"],
            ),
        )
    for i, price in [(1, "20"), (2, "30"), (3, "40"), (8, "0")]:
        await create(
            f"product{i}", "products", dict(name=unique_product_name(f"QA-{i}"), basePrice=price, isFreePrice=i == 8)
        )
    await create("driver0", "drivers", dict(name=f"QA driver {uuid4()}"))
    car = await car_factory(current_mileage=100)
    cards["car0"] = dict(carId=str(car.car_id), currentMileage=100)
    objects["car0"] = dict(id=str(car.car_id))
    settings = PostgresSettings(POSTGRES_DB=test_database_name)
    with psycopg.connect(
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        dbname=test_database_name,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
    ) as connection:
        assert connection.execute("SELECT current_database()").fetchone()[0] == test_database_name
        connection.rollback()
        connection.read_only = True
        before = snapshot(connection)
        for employee in before["employees"]:
            cards[employee["employee_id"]] = dict(
                employeeId=employee["employee_id"],
                isActive=employee["is_active"],
                commissionPercent=employee["commission_percent"],
            )
        prior = None
        scenarios = ["QA-004"] if pickup else ["QA-001", "QA-002", "QA-003"]
        for scenario in scenarios:
            connection.rollback()
            before = snapshot(connection)
            plan = expected_plan(scenario, objects, cards, "QA adapter marker", prior)
            expected = finances(plan, cards)
            base = "/protected/pickup-sheets" if pickup else "/protected/delivery-route-sheets"
            if prior is None:
                payload = {
                    k: v
                    for k, v in clean(plan).items()
                    if k in {"plannedDate", "driverId", "carId", "startMileage", "endMileage"}
                }
                payload["points"] = [
                    {
                        k: v
                        for k, v in p.items()
                        if k in {"clientId", "isDelivered", "nonDeliveryReason", "memo", "paymentMethodId", "items"}
                    }
                    for p in clean(plan)["points"]
                ]
                response = await client.post(base + "/create", json=payload)
                assert response.status_code == 201, response.text
                identity = response.json()["data"]["deliveryDocumentId"]
            else:
                identity = prior["deliveryDocumentId"]
                assert (await client.post(f"{base}/{identity}/edit-lock")).status_code == 200
                points = []
                for point in clean(plan)["points"]:
                    p = {
                        k: v
                        for k, v in point.items()
                        if k in {"pointId", "clientId", "isDelivered", "nonDeliveryReason", "memo", "paymentMethodId"}
                    }
                    p["items"] = point["items"]
                    points.append(p)
                response = await patch_with_revision(client, f"{base}/{identity}", json=dict(points=points))
                assert response.status_code == 200, response.text
            api = (await client.get(f"{base}/{identity}")).json()["data"]
            connection.rollback()
            data = snapshot(connection)
            date = plan["plannedDate"]

            async def history(endpoint, field, date=date):
                result = []
                for offset in range(0, 10000, 100):
                    response = await client.get(
                        endpoint,
                        params=dict(date_from=date, date_to=date, limit=100, offset=offset, include_cancelled="true"),
                    )
                    assert response.status_code == 200, response.text
                    page = response.json()["data"][field]
                    result.extend(page)
                    if len(page) < 100:
                        break
                return result

            checks = Checks()
            verify_document(
                checks,
                scenario,
                dict(plan=plan, expected=expected, before=before, beforeDocument=prior or {}),
                data,
                api,
                await history("/protected/delivery-history", "documents"),
                await history("/protected/client-delivery-history", "deliveries"),
            )
            report = (await client.get("/protected/sales-report", params=dict(date_from=date, date_to=date))).json()[
                "data"
            ]
            Runner.sales(
                SimpleNamespace(live=SimpleNamespace(get=lambda _path, report=report: report)), checks, data, date
            )
            assert checks.passed, [r for r in checks.rows if not r["ok"]]
            assert Decimal(expected["totalAmount"]) == Decimal(
                {"QA-001": "142.50", "QA-002": "169.90", "QA-003": "90.00", "QA-004": "120.00"}[scenario]
            )
            prior = copy.deepcopy(api)
