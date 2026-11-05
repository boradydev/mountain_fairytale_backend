from copy import deepcopy
from decimal import Decimal
from uuid import UUID

import pytest

from src.common.infra.services.event_pud_service import EventPublisher
from src.feat.clients.domain.client_entities import Client
from src.feat.commissions.domain.commission_entities import PointCommission
from src.feat.delivery_document.domain.delivery_document_entities import Point
from src.feat.delivery_document.domain.delivery_document_excs import DeliveryDocumentUpdateException
from src.feat.delivery_document.infra.delivery_document_repos import DeliveryDocumentsRepository
from tests.document_requests import create_delivery, patch_with_revision
from tests.integration.api.test_commissions import commission_case as _commission_case, find, report


commission_case = _commission_case


def correction(case):
    points = [
        {"pointId": row["pointId"], "clientId": row["clientId"], "items": deepcopy(row["items"])}
        for row in case["document"]["points"]
    ]
    points[1]["salesRepresentativeId"] = case["target"]
    return {"expectedRevision": case["document"]["revision"], "points": points}


async def read_state(postgres, case):
    async with postgres.session_factory() as session:
        point_id = UUID(case["document"]["points"][1]["pointId"])
        point = await session.get(Point, point_id)
        entry = await session.get(PointCommission, point_id)
        customer = await session.get(Client, UUID(case["second"]))
        return (
            point.snapshot_sales_representative_id,
            entry.sales_representative_id,
            entry.commission_percent,
            entry.turnover,
            entry.commission_payable,
            customer.sales_representative_id,
        )


async def test_corrects_once_updates_client_audit_and_planned_date_report(
    client, commission_case, postgres, monkeypatch
):
    case = commission_case
    older = await create_delivery(client, json={"plannedDate": "2180-03-01", "points": [case["point"](case["second"])]})
    assert older.status_code == 201
    previous_report = await report(client)
    events = []
    original = EventPublisher.publish_many

    async def capture(self, *, events: list):
        captured.extend(events)
        await original(self, events=events)

    captured = events
    monkeypatch.setattr(EventPublisher, "publish_many", capture)
    assert (await client.post(f"{case['path']}/edit-lock")).status_code == 200
    response = await client.patch(case["path"], json=correction(case))
    assert response.status_code == 200, response.text
    saved = response.json()["data"]
    assert saved["revision"] == case["document"]["revision"] + 1
    assert saved["points"][1]["salesRepresentativeId"] == case["target"]
    assert saved["points"][1]["salesRepresentativeName"]
    target = UUID(case["target"])
    assert await read_state(postgres, case) == (target, target, Decimal(7), Decimal(50), Decimal("3.5"), target)
    changes = [event.changes for event in events if hasattr(event, "changes")]
    assert any("snapshot_sales_representative_id" in change for change in changes)
    assert any("sales_representative_id" in change for change in changes)
    updated_report = await report(client)
    assert find(updated_report["salesRepresentatives"], "salesRepresentativeId", case["rep"]) == find(
        previous_report["salesRepresentatives"], "salesRepresentativeId", case["rep"]
    )
    assert (
        find(updated_report["salesRepresentatives"], "salesRepresentativeId", case["target"])["commissionPayable"]
        == "3.50"
    )
    assert updated_report["employees"] == previous_report["employees"]
    old_path = f"/protected/delivery-route-sheets/{older.json()['data']['deliveryDocumentId']}"
    assert (await client.get(old_path)).json()["data"]["points"][0]["salesRepresentativeId"] is None
    history = await client.get(
        "/protected/client-delivery-history", params={"date_from": "2180-04-15", "date_to": "2180-04-15"}
    )
    assert history.status_code == 200, history.text
    row = next(row for row in history.json()["data"]["deliveries"] if row["pointId"] == saved["points"][1]["pointId"])
    assert row["salesRepresentativeId"] == case["target"]
    repeat = correction(case)
    repeat["expectedRevision"] = saved["revision"]
    repeat["points"][1]["salesRepresentativeId"] = case["rep"]
    assert (await client.patch(case["path"], json=repeat)).status_code == 422
    # A normal save and a changed current rate preserve the captured rate and recipient.
    assert (
        await client.patch(f"/protected/sales-representatives/{case['target']}", json={"commissionPercent": "15"})
    ).status_code == 200
    assert (await patch_with_revision(client, case["path"], json={"plannedDate": "2180-04-15"})).status_code == 200
    assert (await read_state(postgres, case))[2:5] == (Decimal(7), Decimal(50), Decimal("3.5"))
    future = await create_delivery(
        client, json={"plannedDate": "2180-05-01", "points": [case["point"](case["second"])]}
    )
    assert future.json()["data"]["points"][0]["salesRepresentativeId"] == case["target"]


async def test_undelivered_correction_keeps_rate_until_delivery(client, commission_case, postgres):
    case = commission_case
    assert (await client.post(f"{case['path']}/edit-lock")).status_code == 200
    body = correction(case)
    body["points"][1].update(isDelivered=False, nonDeliveryReason="Closed")
    response = await client.patch(case["path"], json=body)
    assert response.status_code == 200, response.text
    assert (await read_state(postgres, case))[2:5] == (Decimal(7), Decimal(0), Decimal(0))
    assert (
        await client.patch(f"/protected/sales-representatives/{case['target']}", json={"commissionPercent": "20"})
    ).status_code == 200
    body["points"][1].pop("salesRepresentativeId")
    body["points"][1].update(isDelivered=True, nonDeliveryReason="")
    body["expectedRevision"] = response.json()["data"]["revision"]
    response = await client.patch(case["path"], json=body)
    assert response.status_code == 200, response.text
    assert (await read_state(postgres, case))[2:5] == (Decimal(7), Decimal(50), Decimal("3.5"))


@pytest.mark.parametrize("failure", ["client", "commission", "flush", "audit"])
async def test_correction_transaction_rolls_back(client, commission_case, postgres, monkeypatch, failure):
    case = commission_case
    before = await read_state(postgres, case)
    assert (await client.post(f"{case['path']}/edit-lock")).status_code == 200

    def fail(*args, **kwargs):
        raise DeliveryDocumentUpdateException(field="points", message="Injected failure")

    async def async_fail(*args, **kwargs):
        fail()

    if failure == "client":
        monkeypatch.setattr(Client, "update", fail)
    elif failure == "commission":
        monkeypatch.setattr(DeliveryDocumentsRepository, "capture_commissions", async_fail)
    elif failure == "flush":
        original = DeliveryDocumentsRepository.update

        async def after_flush(self, document):
            await original(self, document)
            fail()

        monkeypatch.setattr(DeliveryDocumentsRepository, "update", after_flush)
    else:
        monkeypatch.setattr(EventPublisher, "publish_many", async_fail)
    response = await client.patch(case["path"], json=correction(case))
    assert response.status_code == 422, response.text
    assert await read_state(postgres, case) == before
    assert (await client.get(case["path"])).json()["data"]["revision"] == case["document"]["revision"]


@pytest.mark.parametrize(
    "guard",
    [
        "no_lock",
        "revision",
        "cancelled",
        "inactive",
        "missing",
        "null",
        "new",
        "snapshot",
        "recipient",
        "rate",
        "payable",
        "no_commission",
    ],
)
async def test_correction_guards(client, commission_case, postgres, guard):
    case = commission_case
    body = correction(case)
    if guard != "no_lock":
        assert (await client.post(f"{case['path']}/edit-lock")).status_code == 200
    if guard == "revision":
        body["expectedRevision"] += 1
    elif guard == "cancelled":
        assert (await client.post(f"{case['path']}/cancel")).status_code == 200
        body["expectedRevision"] = (await client.get(case["path"])).json()["data"]["revision"]
    elif guard == "inactive":
        assert (
            await client.patch(f"/protected/sales-representatives/{case['target']}", json={"isActive": False})
        ).status_code == 200
    elif guard == "missing":
        from src.core.uuid7 import uuid7

        body["points"][1]["salesRepresentativeId"] = str(uuid7())
    elif guard == "null":
        body["points"][1]["salesRepresentativeId"] = None
    elif guard == "new":
        body["points"][1].pop("pointId")
    elif guard in {"snapshot", "recipient", "rate", "payable", "no_commission"}:
        async with postgres.session_factory() as session:
            point_id = UUID(case["document"]["points"][1]["pointId"])
            entry = await session.get(PointCommission, point_id)
            if guard == "snapshot":
                point = await session.get(Point, point_id)
                point.snapshot_sales_representative_id = UUID(case["rep"])
            elif guard == "recipient":
                entry.sales_representative_id = UUID(case["rep"])
            elif guard == "rate":
                entry.commission_percent = Decimal(1)
            elif guard == "payable":
                entry.commission_payable = Decimal(1)
            else:
                await session.delete(entry)
            await session.commit()
    response = await client.patch(case["path"], json=body)
    assert response.status_code in {409, 422}, response.text
    customer = (await client.get(f"/protected/clients/{case['second']}")).json()["data"]
    assert customer["salesRepresentativeId"] is None


async def test_zero_rate_and_concurrent_correction(client, commission_case, postgres):
    import asyncio

    case = commission_case
    assert (
        await client.patch(f"/protected/sales-representatives/{case['target']}", json={"commissionPercent": "0"})
    ).status_code == 200
    assert (await client.post(f"{case['path']}/edit-lock")).status_code == 200
    first, second = await asyncio.gather(
        client.patch(case["path"], json=correction(case)), client.patch(case["path"], json=correction(case))
    )
    assert sorted([first.status_code, second.status_code]) == [200, 409]
    assert (await read_state(postgres, case))[2:5] == (Decimal(0), Decimal(50), Decimal(0))


async def test_pickup_rejects_correction(client, commission_case):
    response = await client.post(
        "/protected/pickup-sheets/create", json={"plannedDate": "2180-04-15", "points": [{"items": []}]}
    )
    document = response.json()["data"]
    path = f"/protected/pickup-sheets/{document['deliveryDocumentId']}"
    assert (await client.post(f"{path}/edit-lock")).status_code == 200
    response = await client.patch(
        path,
        json={
            "expectedRevision": document["revision"],
            "points": [
                {
                    "pointId": document["points"][0]["pointId"],
                    "items": [],
                    "salesRepresentativeId": commission_case["target"],
                }
            ],
        },
    )
    assert response.status_code == 422, response.text
