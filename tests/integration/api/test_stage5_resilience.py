"""QA-043..047 over native TCP; enable only through the isolated runner."""

import asyncio
import os
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import text

from src.core.uuid7 import uuid7
from tests.integration.api import test_delivery_document_contract as contract
from tests.integration.api.test_delivery_document_routers import TestDeliveryDocumentRouters as API
from tests.integration.api.test_stage5_concurrency import (
    assert_financial_integrity,
    assert_no_open_transactions,
    expire,
)
from tests.resilience_tcp import FaultProxy, NativeAPI


document_case = contract.document_case
pytestmark = [
    pytest.mark.timeout(45),
    pytest.mark.skipif(os.getenv("RESILIENCE_TCP") != "1", reason="isolated runner only"),
]


def financial_patch(case, key):
    points = contract.patch_points(case["document"])
    points[0]["items"][0].update(quantity=3, price=13.25)
    payload = {"expectedRevision": 1, "operationId": key, "plannedDate": "2026-11-10", "points": points}
    if "carId" in case["payload"]:
        payload["endMileage"] = 115
    return payload


@pytest.fixture
async def active_employee(employee_factory):
    return await employee_factory(commission_percent=7.5)


async def snapshot(postgres):
    """Independent complete logical snapshot, including money, mileage, locks and audit."""
    async with postgres.session_factory() as session:
        tables = (await session.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'"))).scalars()
        result = {}
        for table in tables:
            result[table] = (
                (await session.execute(text(f'SELECT row_to_json(t)::text FROM "{table}" t ORDER BY 1')))
                .scalars()
                .all()
            )
        return result


@pytest.fixture
async def native(document_case, active_employee, client, tmp_path):
    api = NativeAPI(tmp_path)
    proxy = FaultProxy(api.port)
    try:
        await api.start()
        await proxy.start()
        async with httpx.AsyncClient(
            base_url=f"http://127.0.0.1:{proxy.port}", headers=client.headers, timeout=5, trust_env=False
        ) as session:
            await API.login(session, active_employee)
            yield api, proxy, session
    finally:
        api.stop()
        if hasattr(proxy, "server"):
            await proxy.close()
        api.log.close()


@pytest.mark.parametrize("mode", ["offline", "partial"])
async def test_disconnect_without_commit(native, document_case, postgres, mode):
    _, proxy, session = native
    before = await snapshot(postgres)
    proxy.mode = mode
    with pytest.raises(httpx.TransportError):
        await session.patch(document_case["path"], json={"expectedRevision": 1, "plannedDate": "2026-11-10"})
    assert await snapshot(postgres) == before
    assert (await session.get(document_case["path"])).json()["data"] == document_case["document"]
    assert (await session.patch(document_case["path"] + "/edit-lock")).status_code == 200
    await assert_no_open_transactions(postgres)


@pytest.mark.parametrize("creating", [True, False])
async def test_response_lost_after_independently_confirmed_commit(
    native, document_case, postgres, active_employee, creating
):
    _, proxy, session = native
    case = document_case
    key = str(uuid7())
    before = await snapshot(postgres)
    payload = {**case["payload"], "creationRequestId": key} if creating else financial_patch(case, key)
    proxy.mode = "lost"
    pending = asyncio.create_task(
        session.request(
            "POST" if creating else "PATCH", case["base"] + "/create" if creating else case["path"], json=payload
        )
    )
    try:
        await asyncio.wait_for(proxy.arrived.wait(), 5)
        # No response has reached the client. A separate PostgreSQL transaction proves COMMIT.
        assert not pending.done()
        async with postgres.session_factory() as db:
            row = (
                await db.execute(
                    text(
                        "SELECT delivery_document_id, revision, last_operation_id FROM delivery_documents WHERE "
                        + ("creation_request_id=:key" if creating else "last_operation_id=:key")
                    ),
                    {"key": key},
                )
            ).one()
            assert row.revision == (1 if creating else 2)
            if not creating:
                assert str(row.last_operation_id) == key
        committed = await snapshot(postgres)
        assert len(committed["delivery_documents"]) == len(before["delivery_documents"]) + int(creating)
        assert len(committed["points"]) == len(before["points"]) + (2 if creating else 0)
        assert len(committed["delivery_document_items"]) == len(before["delivery_document_items"]) + int(creating)
    finally:
        proxy.release.set()
    with pytest.raises(httpx.TransportError):
        await pending
    path = f"{case['base']}/{row.delivery_document_id}"
    recovered = (await session.get(f"{case['base']}/creation-requests/{key}" if creating else path)).json()["data"]
    assert recovered["revision"] == row.revision
    async with postgres.session_factory() as db:
        amounts = (
            await db.execute(
                text(
                    "SELECT i.quantity,i.price FROM delivery_document_items i JOIN points p USING(point_id) "
                    "WHERE p.delivery_document_id=:id"
                ),
                {"id": recovered["deliveryDocumentId"]},
            )
        ).all()
        assert len(amounts) == 1
        assert sum(Decimal(str(q)) * Decimal(str(p)) for q, p in amounts) == Decimal("25" if creating else "39.75")
        if not creating and "carId" in case["payload"]:
            assert (
                await db.scalar(
                    text("SELECT current_mileage FROM cars WHERE car_id=:id"), {"id": case["payload"]["carId"]}
                )
                == 115
            )
    events = await contract.read_events(postgres, recovered)
    assert events
    assert all(str(e["actor_id"]) == str(active_employee.employee_id) for e in events)
    if creating:
        repeated = await session.post(case["base"] + "/create", json=payload)
        assert repeated.status_code in (200, 201)
        assert repeated.json()["data"] == recovered
    assert await snapshot(postgres) == committed
    await assert_financial_integrity(postgres, recovered)
    await assert_no_open_transactions(postgres)


@pytest.mark.parametrize("creating", [True, False])
@pytest.mark.parametrize("kill", [False, True])
async def test_flushed_transaction_rollback_or_owned_process_crash(native, document_case, postgres, creating, kill):
    api, _, session = native
    before = await snapshot(postgres)
    key = str(uuid7())
    api.gate.write_text("armed", encoding="utf-8")
    payload = (
        {**document_case["payload"], "creationRequestId": key} if creating else financial_patch(document_case, key)
    )
    pending = asyncio.create_task(
        session.request(
            "POST" if creating else "PATCH",
            document_case["base"] + "/create" if creating else document_case["path"],
            json=payload,
        )
    )
    try:
        for _ in range(200):
            if api.gate.with_suffix(".reached").exists():
                break
            await asyncio.sleep(0.02)
        assert api.gate.with_suffix(".reached").exists()
        assert await snapshot(postgres) == before
        if kill:
            api.stop()
        api.gate.unlink()
        if kill:
            with pytest.raises(httpx.TransportError):
                await pending
            await api.start()
        else:
            assert (await pending).status_code == 500
        assert await snapshot(postgres) == before
        assert (await session.get(document_case["path"])).json()["data"] == document_case["document"]
        if creating:
            assert (await session.get(f"{document_case['base']}/creation-requests/{key}")).status_code == 404
        assert (await session.patch(document_case["path"] + "/edit-lock")).status_code == 200
        await assert_no_open_transactions(postgres)
    finally:
        if api.gate.exists():
            api.gate.unlink()
        if not pending.done():
            pending.cancel()
        await asyncio.gather(pending, return_exceptions=True)


async def test_restart_tokens_locks_dashboard_and_other_operator(
    native, document_case, postgres, employee_factory, active_employee
):
    api, proxy, a = native
    path = document_case["path"]
    position = (await a.get("/protected/dashboard-updates?timeout=0")).json()["data"]
    before = await snapshot(postgres)
    polling = asyncio.create_task(
        a.get(
            "/protected/dashboard-updates",
            params={"server_id": position["serverId"], "version": position["version"], "timeout": 25},
        )
    )
    for _ in range(200):
        if api.gate.with_suffix(".polling").exists():
            break
        await asyncio.sleep(0.02)
    assert api.gate.with_suffix(".polling").exists()
    assert not polling.done()
    await assert_no_open_transactions(postgres)
    api.stop()
    with pytest.raises(httpx.TransportError):
        await polling
    with pytest.raises(httpx.TransportError):
        await a.get("/health/ready")
    await api.start()
    assert await snapshot(postgres) == before
    assert (await a.get(path)).json()["data"] == document_case["document"]
    refreshed = await a.post("/public/auth/refresh", json={"refreshToken": a.cookies.get("refresh-token")})
    assert refreshed.status_code == 200
    changed = (
        await a.get(
            "/protected/dashboard-updates",
            params={"server_id": position["serverId"], "version": position["version"], "timeout": 0},
        )
    ).json()["data"]
    assert changed["serverId"] != position["serverId"]
    assert changed["reloadRequired"]
    assert changed["clientsChanged"]
    assert changed["deliveryDaysChanged"]
    assert (await a.get("/protected/clients")).status_code == 200
    b_employee = await employee_factory(commission_percent=7.5)
    async with httpx.AsyncClient(base_url=a.base_url, headers=a.headers, trust_env=False) as b:
        await API.login(b, b_employee)
        assert (await b.post(path + "/edit-lock")).status_code == 423
        await expire(postgres, document_case["document"]["deliveryDocumentId"])
        assert (await b.post(path + "/edit-lock")).status_code == 200
        saved = await b.patch(path, json={"expectedRevision": 1, "plannedDate": "2026-11-11"})
        assert saved.status_code == 200
        checkpoint = await snapshot(postgres)
        stale = await a.patch(path, json={"expectedRevision": 1, "plannedDate": "2026-11-12"})
        assert stale.status_code == 409  # Revision is checked before lock ownership.
        assert stale.json()["currentRevision"] == 2
        assert (await b.delete(path + "/edit-lock")).status_code == 200
        assert (await a.post(path + "/edit-lock")).status_code == 200
        stale_before = await snapshot(postgres)
        assert (await a.patch(path, json={"expectedRevision": 1, "plannedDate": "2026-11-12"})).status_code == 409
        assert await snapshot(postgres) == stale_before
        assert (await a.get(path)).json()["data"] == saved.json()["data"]
        assert len(checkpoint["events"]) == len(stale_before["events"])
        events = await contract.read_events(postgres, saved.json()["data"])
        assert str(events[-1]["actor_id"]) == str(b_employee.employee_id)
        await assert_financial_integrity(postgres, saved.json()["data"])
    await assert_no_open_transactions(postgres)


async def test_delay_renewal_and_lost_release(native, document_case, postgres):
    _, proxy, session = native
    path = document_case["path"]
    before = await snapshot(postgres)
    proxy.mode = "offline"
    with pytest.raises(httpx.TransportError):
        await session.patch(path + "/edit-lock")
    assert await snapshot(postgres) == before
    proxy.mode = "delay"
    pending = asyncio.create_task(session.get(path))
    try:
        await asyncio.wait_for(proxy.arrived.wait(), 5)
        assert not pending.done()
        assert await snapshot(postgres) == before
    finally:
        proxy.release.set()
    assert (await pending).json()["data"] == document_case["document"]
    proxy.arrived.clear()
    proxy.release.clear()
    proxy.mode = "lost"
    pending = asyncio.create_task(session.delete(path + "/edit-lock"))
    try:
        await asyncio.wait_for(proxy.arrived.wait(), 5)
        async with postgres.session_factory() as db:
            assert (
                await db.scalar(
                    text("SELECT count(*) FROM delivery_document_edit_locks WHERE delivery_document_id=:id"),
                    {"id": document_case["document"]["deliveryDocumentId"]},
                )
                == 0
            )
    finally:
        proxy.release.set()
    with pytest.raises(httpx.TransportError):
        await pending
    after = await snapshot(postgres)
    assert {k: v for k, v in before.items() if k != "delivery_document_edit_locks"} == {
        k: v for k, v in after.items() if k != "delivery_document_edit_locks"
    }
    assert (await session.post(path + "/edit-lock")).status_code == 200
    await assert_no_open_transactions(postgres)
