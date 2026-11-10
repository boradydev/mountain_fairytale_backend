"""Stage 5: independent operator sessions against migrated PostgreSQL, no DB mocks."""

import asyncio
from contextlib import AsyncExitStack
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from src.common.api.app import fastapi_app
from src.common.infra.services.event_pud_service import EventPublisher
from src.core.uuid7 import uuid7
from tests.helpers import unique_phone
from tests.integration.api import test_delivery_document_contract as contract
from tests.integration.api.test_delivery_document_contract import patch_points, read_events
from tests.integration.api.test_delivery_document_routers import TestDeliveryDocumentRouters as API


document_case = contract.document_case


pytestmark = pytest.mark.timeout(30)


@pytest.fixture
async def operators(client, active_employee, employee_factory):
    employees = [
        active_employee,
        await employee_factory(commission_percent=7.5),
        await employee_factory(commission_percent=3.25),
    ]
    async with AsyncExitStack() as stack:
        sessions = []
        for employee in employees:
            session = await stack.enter_async_context(
                AsyncClient(transport=ASGITransport(app=fastapi_app), base_url=client.base_url, headers=client.headers)
            )
            await API.login(session, employee)
            sessions.append(session)
        yield sessions, employees


async def race(*requests):
    return await asyncio.wait_for(asyncio.gather(*requests), timeout=10)


async def document_race(postgres, document_id, *requests):
    async with postgres.session_factory() as blocker:
        await blocker.execute(
            text("SELECT delivery_document_id FROM delivery_documents WHERE delivery_document_id=:id FOR UPDATE"),
            {"id": document_id},
        )
        tasks = [asyncio.create_task(request) for request in requests]
        try:
            await wait_for_blocked_connections(postgres, len(tasks))
        finally:
            await blocker.rollback()
            responses = await race(*tasks)
    return responses


async def assert_financial_integrity(postgres, document):
    async with postgres.session_factory() as session:
        total = Decimal(0)
        for point in document["points"]:
            rows = (
                await session.execute(
                    text("SELECT quantity,price FROM delivery_document_items WHERE point_id=:id"),
                    {"id": point["pointId"]},
                )
            ).all()
            turnover = sum((Decimal(str(q)) * Decimal(str(p)) for q, p in rows), Decimal(0))
            total += turnover
            commission = (
                await session.execute(
                    text(
                        "SELECT turnover,commission_percent,commission_payable "
                        "FROM point_commissions WHERE point_id=:id"
                    ),
                    {"id": point["pointId"]},
                )
            ).one()
            assert commission.turnover == turnover
            assert commission.commission_payable == turnover * commission.commission_percent / 100
        commissions = (
            await session.execute(
                text(
                    "SELECT turnover,commission_percent,commission_payable FROM document_employee_commissions "
                    "WHERE delivery_document_id=:id"
                ),
                {"id": document["deliveryDocumentId"]},
            )
        ).all()
        assert commissions
        for turnover, percent, payable in commissions:
            assert turnover == total
            assert payable == total * percent / 100


async def expire(postgres, document_id):
    async with postgres.session_factory() as session:
        deadline = datetime.now() - timedelta(seconds=1)
        await session.execute(
            text("UPDATE delivery_document_edit_locks SET expires_at=:deadline WHERE delivery_document_id=:id"),
            {"deadline": deadline, "id": document_id},
        )
        await session.commit()
        assert (
            await session.scalar(
                text("SELECT expires_at FROM delivery_document_edit_locks WHERE delivery_document_id=:id"),
                {"id": document_id},
            )
            == deadline
        )


async def assert_no_open_transactions(postgres):
    async with postgres.session_factory() as session:
        assert (
            await session.scalar(
                text(
                    "SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() "
                    "AND pid<>pg_backend_pid() AND (xact_start IS NOT NULL OR wait_event_type='Lock')"
                )
            )
            == 0
        )


async def test_operator_exclusion_renewal_and_crashed_session(document_case, operators, postgres):
    case = document_case
    (a, b, _), employees = operators
    path = case["path"]
    lock = f"{path}/edit-lock"
    original = case["document"]
    before = await read_events(postgres, original)
    assert (await a.get(path)).json()["data"] == (await b.get(path)).json()["data"] == original
    for request in (b.post(lock), b.patch(path, json={"expectedRevision": 1, "points": []})):
        response = await request
        assert response.status_code == 423
        assert response.json()["ownerName"] == employees[0].username
    assert (await b.patch(lock)).status_code == 403
    assert (await b.delete(lock)).status_code == 403
    async with postgres.session_factory() as session:
        deadline = await session.scalar(
            text("SELECT expires_at FROM delivery_document_edit_locks WHERE delivery_document_id=:id"),
            {"id": original["deliveryDocumentId"]},
        )
    assert 110 < (deadline - datetime.now()).total_seconds() <= 120
    assert (await a.patch(lock)).status_code == 200
    async with postgres.session_factory() as session:
        assert (
            await session.scalar(
                text("SELECT expires_at FROM delivery_document_edit_locks WHERE delivery_document_id=:id"),
                {"id": original["deliveryDocumentId"]},
            )
            > deadline
        )
    assert (await a.get(path)).json()["data"] == original
    assert await read_events(postgres, original) == before
    # No release from A: expire only this test database's lease and read back the write.
    await expire(postgres, original["deliveryDocumentId"])
    assert (await a.patch(path, json={"expectedRevision": 1, "points": []})).status_code == 409
    assert (await b.post(lock)).status_code == 200
    assert (await a.patch(path, json={"expectedRevision": 1, "points": []})).status_code == 423
    saved = await b.patch(path, json={"expectedRevision": 1, "plannedDate": "2026-11-10"})
    assert saved.status_code == 200
    assert saved.json()["data"]["revision"] == 2
    assert saved.json()["data"]["points"] == original["points"]
    events = (await read_events(postgres, original))[len(before) :]
    assert events
    assert all(str(event["actor_id"]) == str(employees[1].employee_id) for event in events)
    assert (await b.delete(lock)).status_code == 200
    assert (await b.delete(lock)).status_code == 409
    assert (await a.post(lock)).status_code == 200
    await assert_no_open_transactions(postgres)


async def test_repeated_three_operator_lock_race(document_case, operators, postgres):
    sessions, employees = operators
    lock = f"{document_case['path']}/edit-lock"
    assert (await sessions[0].delete(lock)).status_code == 200
    for _ in range(5):
        responses = await document_race(
            postgres, document_case["document"]["deliveryDocumentId"], *(session.post(lock) for session in sessions)
        )
        assert sorted(response.status_code for response in responses) == [200, 423, 423]
        winner = next(i for i, response in enumerate(responses) if response.status_code == 200)
        assert all(
            (response.json()["data"] if i == winner else response.json())["ownerName"] == employees[winner].username
            for i, response in enumerate(responses)
        )
        assert (await sessions[winner].delete(lock)).status_code == 200
    await assert_no_open_transactions(postgres)


async def test_repeated_revision_race_is_atomic(document_case, operators, postgres):
    case = document_case
    (a, _, _), employees = operators
    # A second connection with the same employee represents an overlapping save/retry.
    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url=a.base_url, headers=a.headers) as retry:
        await API.login(retry, employees[0])
        current = case["document"]
        for iteration in range(5):
            quantities = (3 + 10 * iteration, 7 + 10 * iteration)
            revision = current["revision"]
            payloads = []
            for quantity in quantities:
                points = patch_points(current)
                points[0]["items"][0].update(quantity=quantity, price=13.25)
                payloads.append({"expectedRevision": revision, "operationId": str(uuid7()), "points": points})
            responses = await document_race(
                postgres,
                current["deliveryDocumentId"],
                a.patch(case["path"], json=payloads[0]),
                retry.patch(case["path"], json=payloads[1]),
            )
            assert sorted(response.status_code for response in responses) == [200, 409]
            winner = next(i for i, response in enumerate(responses) if response.status_code == 200)
            loser = responses[1 - winner]
            assert loser.json()["currentRevision"] == revision + 1
            current = (await a.get(case["path"])).json()["data"]
            assert current == responses[winner].json()["data"]
            assert current["revision"] == revision + 1
            assert current["lastOperationId"] == payloads[winner]["operationId"]
            assert current["points"][0]["items"][0]["quantity"] == quantities[winner]
            async with postgres.session_factory() as session:
                rows = (
                    await session.execute(
                        text(
                            "SELECT i.quantity,i.price FROM delivery_document_items i JOIN points p USING(point_id) "
                            "WHERE p.delivery_document_id=:id"
                        ),
                        {"id": current["deliveryDocumentId"]},
                    )
                ).all()
                assert len(rows) == 1
                assert sum(Decimal(str(q)) * Decimal(str(p)) for q, p in rows) == Decimal(quantities[winner]) * Decimal(
                    "13.25"
                )
                assert (
                    await session.scalar(
                        text("SELECT count(*) FROM points WHERE delivery_document_id=:id"),
                        {"id": current["deliveryDocumentId"]},
                    )
                    == 2
                )
            # No-op records its operation ID without changing revision or audit.
            events = await read_events(postgres, current)
            response = await a.patch(
                case["path"],
                json={
                    "expectedRevision": revision + 1,
                    "operationId": current["lastOperationId"],
                    "points": patch_points(current),
                },
            )
            assert response.status_code == 200
            assert response.json()["data"] == current
            assert await read_events(postgres, current) == events
            await assert_financial_integrity(postgres, current)
    await assert_no_open_transactions(postgres)


async def test_cancel_save_race_and_restore(document_case, operators, postgres):
    case = document_case
    (a, b, _), _employees = operators
    path = case["path"]
    for action in ("cancel", "restore"):
        assert (await b.post(f"{path}/{action}")).status_code == 423
    for iteration in range(5):
        current = (await a.get(path)).json()["data"]
        responses = await document_race(
            postgres,
            current["deliveryDocumentId"],
            a.post(f"{path}/cancel"),
            a.patch(path, json={"expectedRevision": current["revision"], "plannedDate": f"2026-11-{11 + iteration}"}),
        )
        # Status commands do not accept expectedRevision. PATCH-first may commit both in order.
        assert responses[0].status_code == 200
        assert responses[1].status_code in (200, 409, 422)
        saved = (await a.get(path)).json()["data"]
        patch_committed = responses[1].status_code == 200
        assert saved["revision"] == current["revision"] + 1 + int(patch_committed)
        assert saved["plannedDate"] == (f"2026-11-{11 + iteration}" if patch_committed else current["plannedDate"])
        assert saved["isActive"] is False
        assert saved["lastOperationId"] is None
        assert saved["points"] == current["points"]
        if saved["isActive"]:
            assert (await a.post(f"{path}/cancel")).status_code == 200
            saved = (await a.get(path)).json()["data"]
        assert (await a.post(f"{path}/cancel")).json()["data"] == saved
        assert (await a.post(f"{path}/edit-lock")).status_code == 409
        restored = await b.post(f"{path}/restore")
        assert restored.status_code == 200
        restored = restored.json()["data"]
        assert restored["revision"] == saved["revision"] + 1
        assert restored["points"] == current["points"]
        assert (await b.post(f"{path}/restore")).json()["data"] == restored
        await assert_financial_integrity(postgres, restored)
        assert (await a.post(f"{path}/edit-lock")).status_code == 200
    await assert_no_open_transactions(postgres)


async def wait_for_blocked_connections(postgres, count):
    async def wait():
        while True:
            async with postgres.session_factory() as observer:
                waiting = await observer.scalar(
                    text(
                        "SELECT count(DISTINCT pid) FROM pg_stat_activity "
                        "WHERE datname=current_database() AND wait_event_type='Lock'"
                    )
                )
            if waiting >= count:
                return
            await asyncio.sleep(0.01)

    await asyncio.wait_for(wait(), 5)


@pytest.mark.parametrize("document_case", ["/protected/delivery-route-sheets"], indirect=True)
async def test_three_routes_share_car_with_real_overlapping_transactions(document_case, operators, postgres):
    case = document_case
    sessions, employees = operators
    documents = [case["document"]]
    paths = [case["path"]]
    for session in sessions[1:]:
        response = await session.post(f"{case['base']}/create", json=case["payload"])
        assert response.status_code == 201
        document = response.json()["data"]
        documents.append(document)
        paths.append(f"{case['base']}/{document['deliveryDocumentId']}")
        assert (await session.post(f"{paths[-1]}/edit-lock")).status_code == 200
    for iteration in range(5):
        mileages = [400 + iteration * 1000, 300 + iteration * 1000, 500 + iteration * 1000]
        async with postgres.session_factory() as blocker:
            await blocker.execute(
                text("SELECT car_id FROM cars WHERE car_id=:id FOR UPDATE"), {"id": documents[0]["carId"]}
            )
            tasks = [
                asyncio.create_task(
                    session.patch(
                        path,
                        json={
                            "expectedRevision": iteration + 1,
                            "endMileage": mileage,
                        },
                    )
                )
                for session, path, mileage in zip(sessions, paths, mileages, strict=True)
            ]
            try:
                # Three distinct backend PIDs must simultaneously wait on the real car row lock.
                await wait_for_blocked_connections(postgres, 3)
            finally:
                await blocker.rollback()
                responses = await race(*tasks)
        assert [response.status_code for response in responses] == [200, 200, 200]
        async with postgres.session_factory() as observer:
            assert await observer.scalar(
                text("SELECT current_mileage FROM cars WHERE car_id=:id"), {"id": documents[0]["carId"]}
            ) == max(mileages)
        for index, (session, path) in enumerate(zip(sessions, paths, strict=True)):
            current = (await session.get(path)).json()["data"]
            assert current["revision"] == iteration + 2
            assert current["endMileage"] == mileages[index]
            assert current["points"] == documents[index]["points"]
            await assert_financial_integrity(postgres, current)
            events = await read_events(postgres, current)
            assert all(str(event["actor_id"]) == str(employees[index].employee_id) for event in events)
    await assert_no_open_transactions(postgres)


async def test_locked_document_does_not_block_unrelated_document(document_case, operators, postgres):
    case = document_case
    (a, b, _), _employees = operators
    # Always exercise a pickup as the unrelated document, alongside route/pickup parameterization.
    response = await b.post(
        "/protected/pickup-sheets/create",
        json={
            "plannedDate": "2026-11-10",
            "points": [{"clientId": None, "items": []}],
        },
    )
    assert response.status_code == 201
    other = response.json()["data"]
    other_path = f"/protected/pickup-sheets/{other['deliveryDocumentId']}"
    assert (await b.post(f"{other_path}/edit-lock")).status_code == 200
    async with postgres.session_factory() as blocker:
        await blocker.execute(
            text("SELECT delivery_document_id FROM delivery_documents WHERE delivery_document_id=:id FOR UPDATE"),
            {"id": case["document"]["deliveryDocumentId"]},
        )
        waiting = asyncio.create_task(a.patch(case["path"], json={"expectedRevision": 1, "plannedDate": "2026-11-13"}))
        try:
            await wait_for_blocked_connections(postgres, 1)
            response = await asyncio.wait_for(
                b.patch(
                    other_path,
                    json={
                        "expectedRevision": 1,
                        "plannedDate": "2026-11-14",
                    },
                ),
                3,
            )
            assert response.status_code == 200
            assert response.json()["data"]["revision"] == 2
            assert not waiting.done()
        finally:
            await blocker.rollback()
            assert (await asyncio.wait_for(waiting, 5)).status_code == 200
    await assert_no_open_transactions(postgres)


async def position(session, previous=None, timeout=0):
    params = {"timeout": timeout}
    if previous:
        params.update(server_id=previous["serverId"], version=previous["version"])
    response = await session.get("/protected/dashboard-updates", params=params)
    assert response.status_code == 200
    return response.json()["data"]


async def test_dashboard_does_not_publish_uncommitted_changes(document_case, operators, postgres, monkeypatch):
    (a, b, _), _employees = operators
    case = document_case
    previous = await position(b)
    original_publish = EventPublisher.publish_many
    ready, proceed = asyncio.Event(), asyncio.Event()

    async def pause_before_commit(self, *, events):
        await original_publish(self, events=events)
        ready.set()
        await asyncio.wait_for(proceed.wait(), 5)

    with monkeypatch.context() as patch:
        patch.setattr(EventPublisher, "publish_many", pause_before_commit)
        saving = asyncio.create_task(
            a.patch(
                case["path"],
                json={
                    "expectedRevision": 1,
                    "plannedDate": "2026-11-15",
                },
            )
        )
        try:
            await asyncio.wait_for(ready.wait(), 3)
            before = await position(b, previous, 0.05)
            assert before["version"] == previous["version"]
            assert not before["clientsChanged"]
            assert not before["deliveryDaysChanged"]
            # The writer has flushed document and events; another real connection still sees the old revision.
            assert (await b.get(case["path"])).json()["data"] == case["document"]
        finally:
            proceed.set()
            assert (await asyncio.wait_for(saving, 5)).status_code == 200
    committed = await position(b, previous)
    assert committed["version"] == previous["version"] + 1
    assert committed["clientsChanged"]
    assert committed["deliveryDaysChanged"]
    assert (await b.get(case["path"])).json()["data"]["revision"] == 2
    await assert_no_open_transactions(postgres)


async def test_dashboard_commit_rollback_and_missed_versions(document_case, operators, postgres, monkeypatch):
    (a, b, _), _employees = operators
    case = document_case
    initial = await position(a)
    assert initial["reloadRequired"]
    assert initial["clientsChanged"]
    assert initial["deliveryDaysChanged"]
    assert not (await position(a, initial, 0.05))["clientsChanged"]
    for method in (b.post, b.patch, b.delete):
        # Foreign lock actions also must never notify.
        await method(f"{case['path']}/edit-lock")
    for method in (a.patch, a.delete, a.post):
        assert (await method(f"{case['path']}/edit-lock")).status_code == 200
    assert await position(a, initial) == {
        **initial,
        "reloadRequired": False,
        "clientsChanged": False,
        "deliveryDaysChanged": False,
    }
    pending = asyncio.create_task(position(a, initial, 2))
    await asyncio.sleep(0.05)
    assert not pending.done()
    await assert_no_open_transactions(postgres)
    created = await b.post(
        "/protected/clients/create",
        json={
            "name": f"Concurrency {uuid7()}",
            "phone": unique_phone(),
            "deliveryAddress": case["customers"][0]["deliveryAddress"],
            "sleepingThresholdDays": 10,
        },
    )
    assert created.status_code == 201, created.text
    update = await asyncio.wait_for(pending, 3)
    assert update["clientsChanged"]
    assert not update["deliveryDaysChanged"]
    assert not update["reloadRequired"]
    client_path = f"/protected/clients/{created.json()['data']['clientId']}"
    for payload in ({"name": f"Changed {uuid7()}"}, {"isActive": False}):
        previous = await position(a)
        assert (await b.patch(client_path, json=payload)).status_code == 200
        changed = await position(a, previous)
        assert changed["clientsChanged"]
        assert not changed["deliveryDaysChanged"]
    previous = await position(a)
    created_doc = await b.post(f"{case['base']}/create", json=case["payload"])
    assert created_doc.status_code == 201
    changed = await position(a, previous)
    assert changed["clientsChanged"]
    assert changed["deliveryDaysChanged"]
    assert (await a.patch(case["path"], json={"expectedRevision": 1, "plannedDate": "2026-11-12"})).status_code == 200
    missed = await position(a, initial)
    assert missed["version"] > update["version"]
    assert missed["clientsChanged"]
    assert missed["deliveryDaysChanged"]
    baseline = (await a.get(case["path"])).json()["data"]
    events = await read_events(postgres, baseline)
    previous = await position(a)

    async def fail_publish(*args, **kwargs):
        raise RuntimeError("concurrency rollback probe")

    with monkeypatch.context() as patch:
        patch.setattr(EventPublisher, "publish_many", fail_publish)
        with pytest.raises(RuntimeError, match="concurrency rollback probe"):
            await a.patch(case["path"], json={"expectedRevision": 2, "points": []})
    after = await position(a, previous, 0.05)
    assert after["version"] == previous["version"]
    assert not after["clientsChanged"]
    assert not after["deliveryDaysChanged"]
    assert (await a.get(case["path"])).json()["data"] == baseline
    assert await read_events(postgres, baseline) == events
    assert (await a.patch(f"{case['path']}/edit-lock")).status_code == 200
    await assert_no_open_transactions(postgres)
