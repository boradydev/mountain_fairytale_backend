"""Seed orchestration tests use disposable in-memory HTTP/SQL doubles, never QA DB."""

import copy
import json
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import httpx
import pytest

from scripts.qa import manage as q
from scripts.qa.seed import Seed, save
from scripts.qa.seed_plan import TABLES, VERSION, catalogs, clients, documents, expectations


class MemorySeed(Seed):
    def __init__(self, path, store):
        super().__init__({}, MagicMock(), SimpleNamespace(), path)
        self.store = store
        self.writes = 0

    def guard(self):
        self.revision = "test-head"

    def login(self):
        pass

    def inventory(self):
        known = {o["id"] for o in self.state["objects"].values()} if self.state else set()
        if self.state and self.state.get("pending"):
            known |= {v["id"] for v in self.store.values() if v["request"] == self.state["pending"]["body"]}
        q.require(all(v["id"] in known for v in self.store.values()), "Unknown business data")

    def validate(self):
        self.state["validation"] = {"result": "test-double"}

    def request(self, method, path, body=None):
        _, _, kind, identity, *rest = path.split("/")
        if method == "GET":
            return copy.deepcopy(self.store[identity]["response"])
        self.writes += 1
        if identity == "create":
            request = copy.deepcopy(body)
            request.pop("password", None)
            prior = next(
                (v for v in self.store.values() if body.get("creationRequestId") and v["request"] == request), None
            )
            if prior:
                return copy.deepcopy(prior["response"])
            identity = str(uuid4())
            pk = TABLES[kind][1].split("_")
            key = pk[0] + "".join(x.title() for x in pk[1:])
            response = copy.deepcopy(request) | {key: identity, "isActive": True}
            if "points" in body:
                response |= {"revision": 1, "createdAt": "2026-11-07T12:00:00"}
                for p in response["points"]:
                    p["pointId"] = str(uuid4())
                    for i in p["items"]:
                        i["itemId"] = str(uuid4())
            self.store[identity] = dict(id=identity, request=request, response=response)
        else:
            response = self.store[identity]["response"]
            response.update(body or {"isActive": False})
        return copy.deepcopy(response)


@pytest.fixture
def memory(tmp_path):
    return MemorySeed(tmp_path / "manifest.json", {})


def test_full_seed_repeat_preserves_core_and_changed_manual(memory):
    memory.run()
    assert memory.state["complete"]
    assert len(memory.state["objects"]) == 64
    before = copy.deepcopy(memory.store)
    manual = memory.state["objects"]["client20"]["id"]
    memory.store[manual]["response"]["name"] = "Owner edit"
    repeat = MemorySeed(memory.path, memory.store)
    repeat.run()
    assert repeat.writes == 0
    assert repeat.store[manual]["response"]["name"] == "Owner edit"
    assert all(repeat.store[k] == v for k, v in before.items() if k != manual)


def test_changed_core_refuses_without_writes(memory):
    memory.run()
    core = memory.state["objects"]["client0"]["id"]
    memory.store[core]["response"]["name"] = "Unexpected edit"
    repeat = MemorySeed(memory.path, memory.store)
    with pytest.raises(RuntimeError, match="changed"):
        repeat.run()
    assert repeat.writes == 0


def test_partial_failure_before_http_can_continue(memory, monkeypatch):
    original = memory.create

    def fail(key, *args, **kwargs):
        if key == "product2":
            raise RuntimeError("controlled failure")
        return original(key, *args, **kwargs)

    monkeypatch.setattr(memory, "create", fail)
    with pytest.raises(RuntimeError, match="controlled"):
        memory.run()
    count = len(memory.store)
    repeat = MemorySeed(memory.path, memory.store)
    repeat.run()
    assert repeat.state["complete"]
    assert len(repeat.store) == 64 > count


def test_unknown_data_refuses(memory):
    memory.store["unknown"] = dict(id="unknown")
    with pytest.raises(RuntimeError, match="Unknown"):
        memory.run()
    assert memory.writes == 0
    assert not memory.path.exists()


def test_actual_inventory_refuses_unknown(tmp_path):
    connection = MagicMock()
    connection.execute.return_value.fetchall.return_value = [(uuid4(),)]
    seed = Seed({}, connection, None, tmp_path / "manifest.json")
    with pytest.raises(RuntimeError, match="Unknown business data"):
        seed.inventory()


def test_version_conflict(tmp_path):
    path = tmp_path / "manifest.json"
    save(path, dict(version="unknown"))
    with pytest.raises(RuntimeError, match="Conflicting"):
        Seed({}, None, None, path)


def test_http_target_refused_before_write(tmp_path, monkeypatch):
    monkeypatch.setattr(q, "verify", lambda *_: None)
    with httpx.Client(base_url="https://example.invalid") as client:
        seed = Seed({}, None, client, tmp_path / "manifest.json")
        with pytest.raises(RuntimeError, match="Wrong HTTP target"):
            seed.guard()


@pytest.mark.parametrize("message", ["Actual database mismatch", "QA marker missing or mismatched"])
def test_identity_failure_before_http(tmp_path, monkeypatch, message):
    def refuse(*_):
        raise RuntimeError(message)

    monkeypatch.setattr(q, "verify", refuse)
    client = MagicMock()
    seed = Seed({}, None, client, tmp_path / "manifest.json")
    with pytest.raises(RuntimeError, match=message):
        seed.run()
    client.request.assert_not_called()
    client.post.assert_not_called()


def test_manifest_no_secrets_and_expected_inputs(memory):
    memory.run()
    raw = memory.path.read_text(encoding="utf-8")
    assert all(secret not in raw for secret in ['"password"', '"accessToken"', '"QA_MARKER"'])
    assert memory.state["version"] == VERSION
    assert memory.state["alembicRevision"] == "test-head"
    assert len({o["id"] for o in memory.state["objects"].values()}) == 64
    rounded = memory.state["objects"]["route2"]["expected"]["points"][0]
    assert rounded["lineAmounts"] == ["1.01", "1.01"]
    assert rounded["totalAmount"] == "2.02"


def test_independent_finances_failed_free_and_rounding():
    payload = dict(
        points=[
            dict(
                clientId="client",
                items=[
                    dict(productId="ordinary", quantity=1, price="1.005"),
                    dict(productId="ordinary2", quantity=1, price="1.005"),
                    dict(productId="free", quantity=9, price="0", isFreePrice=True),
                    dict(productId="free", quantity=3, price="7.125", isFreePrice=True),
                    dict(productId="gift", quantity=4, price="0"),
                ],
            ),
            dict(clientId="client", isDelivered=False, items=[dict(productId="ordinary", quantity=2, price="100")]),
        ]
    )
    exp = expectations(payload, {"client": ("rep", "2.5")}, {"employee": "1.25"})
    assert exp["totalAmount"] == "23.40"
    assert exp["points"][1]["totalAmount"] == "200.00"
    assert exp["points"][1]["commission"] == "0.0"
    assert exp["points"][0]["salesIncluded"] == [True, True, False, True, True]
    assert exp["warehouse"] == {"ordinary": 3, "ordinary2": 1, "gift": 4}
    assert Decimal(exp["employees"]["employee"]["commission"]) == Decimal("0.2925")


def test_fixed_plan_counts_dates_and_anonymous_pickups():
    objects = {}
    for key, kind, body, group in catalogs():
        objects[key] = dict(id=key, kind=kind, initial=body, group=group)
    for key, kind, body, group in clients(objects):
        objects[key] = dict(id=key, kind=kind, initial=body, group=group)
    docs = list(documents(objects, date(2026, 11, 7)))
    assert len(docs) == 11
    assert len([o for o in objects.values() if o["kind"] == "clients" and o["group"] == "CORE"]) == 20
    assert all(p["clientId"] is None for _, kind, d in docs if kind == "pickup-sheets" for p in d["points"])
    assert {d["plannedDate"][:7] for _, _, d in docs} == {"2026-11", "2026-10", "2026-09"}
    assert len(json.dumps(docs)) > 0


@pytest.mark.parametrize("failed_key", ["payment0", "route0"])
def test_response_lost_after_commit_recovers_without_duplicate(memory, monkeypatch, failed_key):
    record = memory.record

    def crash(pending, response):
        if pending["key"] == failed_key:
            raise RuntimeError("response lost after commit")
        record(pending, response)

    monkeypatch.setattr(memory, "record", crash)
    with pytest.raises(RuntimeError, match="response lost"):
        memory.run()
    pending = memory.state["pending"]
    existing = next(v for v in memory.store.values() if v["request"] == pending["body"])
    repeat = MemorySeed(memory.path, memory.store)
    repeat.c.execute.return_value.fetchall.return_value = [(existing["id"],)]
    repeat.run()
    assert repeat.state["objects"][failed_key]["id"] == existing["id"]
    assert len(repeat.store) == 64


@pytest.mark.parametrize("committed", [True, False])
def test_interrupted_mutation_reconciles_readback(memory, committed):
    memory.run()
    obj = memory.state["objects"]["client0"]
    desired = {"name": "QA-CORE-Recovery"}
    memory.state["pending"] = dict(
        step="probe", key="client0", method="PATCH", path=f"/protected/clients/{obj['id']}", desired=desired
    )
    memory.persist()
    if committed:
        memory.store[obj["id"]]["response"].update(desired)
    repeat = MemorySeed(memory.path, memory.store)
    repeat.recover_pending()
    assert ("probe" in repeat.state["steps"]) == committed
    assert repeat.state["pending"] is None
    assert repeat.writes == 0


def test_conflicting_interrupted_mutation_refuses(memory):
    memory.run()
    obj = memory.state["objects"]["client0"]
    memory.state["pending"] = dict(
        step="probe", key="client0", method="PATCH", path=f"/protected/clients/{obj['id']}", desired={"name": "Desired"}
    )
    memory.persist()
    memory.store[obj["id"]]["response"]["name"] = "Unexpected concurrent edit"
    repeat = MemorySeed(memory.path, memory.store)
    with pytest.raises(RuntimeError, match="conflicts"):
        repeat.recover_pending()
    assert repeat.writes == 0


@pytest.mark.parametrize("core_points", [0, 1])
def test_actual_inventory_preserves_manual_documents_refuses_core_dependencies(tmp_path, core_points):
    document_id = uuid4()
    cursor = MagicMock()

    def execute(query, params=None):
        text = query.as_string() if hasattr(query, "as_string") else query
        cursor.fetchall.return_value = [(document_id,)] if 'FROM "delivery_documents"' in text else []
        cursor.fetchone.return_value = (core_points,)
        return cursor

    connection = MagicMock()
    connection.execute.side_effect = execute
    path = tmp_path / "manifest.json"
    save(path, dict(version=VERSION, database=q.DB, objects={}, complete=True))
    seed = Seed({}, connection, None, path)
    before = path.read_bytes()
    if core_points:
        with pytest.raises(RuntimeError, match="CORE"):
            seed.inventory()
    else:
        seed.inventory()
    assert path.read_bytes() == before


def test_plan_passes_current_pydantic_contract(memory):
    from src.feat.delivery_document.api.delivery_document_schemas import (
        CreateDeliveryRouteSheetReq,
        CreatePickupSheetReq,
    )

    memory.run()
    for obj in memory.state["objects"].values():
        if obj["kind"] == "delivery-route-sheets":
            CreateDeliveryRouteSheetReq.model_validate(obj["initial"])
        elif obj["kind"] == "pickup-sheets":
            parsed = CreatePickupSheetReq.model_validate(obj["initial"])
            assert all(not p.memo for p in parsed.points)
