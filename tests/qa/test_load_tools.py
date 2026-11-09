"""Load tooling tests: no database/server creation and no integration autouse fixtures."""

import json
import runpy
from contextlib import nullcontext
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID

import httpx
import pytest

from scripts.load import manage, plan
from scripts.load.benchmark import statistics_for
from scripts.load.seed import LoadSeed
from scripts.load.verify import equal, pages
from scripts.qa.seed_plan import expectations
from src.common.infra.db.postgres.alembic import load_guard as guard


def identity():
    return [guard.DB, guard.HOST, guard.PORT, guard.ROLE, guard.ROLE, False, guard.ROLE, "postgres"]


def config():
    return {"LOAD_ALLOW": "local-load-only", "LOAD_MARKER": "secret-marker"}


@pytest.mark.parametrize("failure", [None, "ready", "login", "body"])
def test_managed_http_client_opens_once_and_always_closes(monkeypatch, tmp_path, failure):
    state = tmp_path / "process.json"
    state.write_text(json.dumps({"run_id": "nonce"}), encoding="utf-8")
    monkeypatch.setattr(manage, "STATE", state)
    paths = []

    def handler(request):
        paths.append(request.url.path)
        if request.url.path == "/health/ready":
            return httpx.Response(503 if failure == "ready" else 200, headers={"X-Load-Run": "nonce"})
        assert request.url.path == "/public/auth/login"
        return httpx.Response(401 if failure == "login" else 200, json={"data": {"accessToken": "test-token"}})

    client = httpx.Client(base_url=manage.BASE_URL, transport=httpx.MockTransport(handler))
    monkeypatch.setattr(manage.httpx, "Client", lambda **_kwargs: client)

    def use_client():
        with manage.http_client({"ADMIN_USERNAME": "load_admin", "ADMIN_PASSWORD": "test-password"}) as opened:
            assert opened is client
            assert not opened.is_closed
            assert opened.headers["Authorization"] == "Bearer test-token"
            if failure == "body":
                raise RuntimeError("Caller failed")

    if failure:
        message = {"ready": "attestation", "login": "login", "body": "Caller failed"}[failure]
        with pytest.raises(RuntimeError, match=message):
            use_client()
    else:
        use_client()
    assert client.is_closed
    assert paths == (["/health/ready"] if failure == "ready" else ["/health/ready", "/public/auth/login"])


@pytest.mark.parametrize(
    ("position", "value"),
    [
        (0, "production"),
        (0, "mountain_fairytale_qa"),
        (0, "mountain_fairytale_test"),
        (0, "unknown"),
        (1, "127.0.0.2"),
        (2, 5433),
        (3, "postgres"),
        (4, "postgres"),
        (5, True),
        (6, "postgres"),
        (7, guard.ROLE),
    ],
)
def test_real_identity_rejected(position, value):
    row = identity()
    row[position] = value
    with pytest.raises(RuntimeError, match="mismatch"):
        guard.validate(config(), row, ["secret-marker"], True)


@pytest.mark.parametrize(
    ("tokens", "readonly"),
    [
        ([], True),
        (["wrong"], True),
        (["secret-marker", "secret-marker"], True),
        (["secret-marker"], False),
        ([None], True),
    ],
)
def test_marker_rejected(tokens, readonly):
    with pytest.raises(RuntimeError, match="marker"):
        guard.validate(config(), identity(), tokens, readonly)


def test_missing_authorization():
    with pytest.raises(RuntimeError, match="authorization"):
        guard.validate({}, identity(), ["secret-marker"], True)


def test_guard_uses_supplied_connection():
    c = MagicMock()
    c.execute.side_effect = [
        SimpleNamespace(fetchone=lambda: identity()),
        SimpleNamespace(fetchall=lambda: [("secret-marker",)]),
        SimpleNamespace(fetchone=lambda: (True,)),
    ]
    guard.verify(c, config())
    assert c.execute.call_count == 3


def test_init_confirmation_before_connect(monkeypatch):
    connect = MagicMock(side_effect=AssertionError("must not connect"))
    monkeypatch.setattr(manage.psycopg, "connect", connect)
    with pytest.raises(RuntimeError, match="confirm"):
        manage.initialize(None)
    connect.assert_not_called()


@pytest.mark.parametrize("failure", [None, "database", "role", "marker", "offline", "no_flag", "combined"])
def test_real_alembic_entry_refuses_before_transition(monkeypatch, failure):
    import logging.config

    import sqlalchemy
    from alembic import context
    from alembic.config import Config

    from src.common.infra.db.postgres import settings

    for key in list(__import__("os").environ):
        if key.startswith(("LOAD_", "QA_")):
            monkeypatch.delenv(key)
    for key, val in config().items():
        monkeypatch.setenv(key, val)
    monkeypatch.setenv("POSTGRES_DB", guard.DB)
    args = {} if failure == "no_flag" else {"load_guard": "1"}
    if failure == "combined":
        args["qa_guard"] = "1"
    monkeypatch.setattr(context, "config", Config(), raising=False)
    monkeypatch.setattr(context, "get_x_argument", lambda **_: args)
    monkeypatch.setattr(context, "is_offline_mode", lambda: failure == "offline")
    monkeypatch.setattr(context, "configure", MagicMock())
    monkeypatch.setattr(context, "begin_transaction", nullcontext)
    transition = MagicMock()
    monkeypatch.setattr(context, "run_migrations", transition)
    monkeypatch.setattr(logging.config, "fileConfig", lambda *_: None)
    monkeypatch.setattr(
        settings, "PostgresSettings", lambda: SimpleNamespace(DB_URL_SYNC="postgresql+psycopg://unused")
    )
    row = identity()
    if failure == "database":
        row[0] = "mountain_fairytale_qa"
    if failure == "role":
        row[3] = "postgres"
    c = MagicMock()
    c.begin.side_effect = nullcontext
    c.execute.side_effect = [
        SimpleNamespace(one=lambda: row),
        SimpleNamespace(
            scalars=lambda: SimpleNamespace(all=lambda: ["wrong" if failure == "marker" else "secret-marker"])
        ),
        SimpleNamespace(scalar_one=lambda: True),
    ]
    engine = MagicMock()
    engine.connect.return_value = nullcontext(c)
    monkeypatch.setattr(sqlalchemy, "engine_from_config", lambda *_a, **_kw: engine)
    env_path = manage.ALEMBIC.parent / "migrations/env.py"
    if failure:
        with pytest.raises(Exception, match="[Ll]oad|[Qq][Aa]"):
            runpy.run_path(str(env_path))
        transition.assert_not_called()
    else:
        runpy.run_path(str(env_path))
        transition.assert_called_once()
        assert c.execute.call_count == 3


def objects():
    result = {}
    for i, (key, kind, body, group) in enumerate(plan.directories(), 1):
        result[key] = dict(id=str(UUID(int=i)), kind=kind, initial=body, group=group)
    for i, (key, kind, body, group) in enumerate(plan.clients(result, 5000), 100):
        result[key] = dict(id=str(UUID(int=i)), kind=kind, initial=body, group=group)
    return result


@pytest.mark.parametrize("profile", ["main", "high"])
def test_profile_counts_distribution_and_determinism(profile):
    prepared = objects()
    first = list(plan.documents(prepared, profile, 42))
    second = list(plan.documents(prepared, profile, 42))
    assert first == second
    assert first != list(plan.documents(prepared, profile, 43))
    assert len(first) == plan.PROFILES[profile][1]
    assert sum(len(row[2]["points"]) for row in first) == len(first) * 3
    assert sum(len(p["items"]) for row in first for p in row[2]["points"]) == len(first) * 6
    assert {row[2]["plannedDate"][:7] for row in first} == {f"2026-{n:02}" for n in range(1, 13)}
    assert sum(row[2]["plannedDate"] == "2026-06-15" for row in first) > 300
    used = {p["clientId"] for row in first for p in row[2]["points"] if p["clientId"]}
    assert prepared[f"client{plan.PROFILES[profile][0] - 1}"]["id"] not in used
    for _, kind, body in first:
        if kind == "pickup-sheets":
            assert all(p["memo"] == "" and p["isDelivered"] and p["nonDeliveryReason"] == "" for p in body["points"])
            assert all(p["clientId"] is None and not any(i["isFreePrice"] for i in p["items"]) for p in body["points"])


def test_generated_payloads_follow_request_schemas():
    from src.feat.delivery_document.api.delivery_document_schemas import (
        CreateDeliveryRouteSheetReq,
        CreatePickupSheetReq,
    )

    for _, kind, body in list(plan.documents(objects(), "main", 42))[:30]:
        schema = CreatePickupSheetReq if kind == "pickup-sheets" else CreateDeliveryRouteSheetReq
        schema.model_validate(body)


def test_independent_money_and_commissions():
    payload = {
        "points": [
            {
                "clientId": "c",
                "items": [
                    {"productId": "p", "quantity": 1, "price": "1.005"},
                    {"productId": "f", "quantity": 3, "price": "7.125", "isFreePrice": True},
                ],
            },
            {"clientId": "c", "isDelivered": False, "items": [{"productId": "p", "quantity": 5, "price": "10"}]},
        ]
    }
    result = expectations(payload, {"c": ("r", "2.5")}, {"e": "1.25"})
    assert result["totalAmount"] == "22.39"
    assert Decimal(result["points"][0]["commission"]) == Decimal("0.55975")
    assert Decimal(result["points"][1]["commission"]) == 0
    assert Decimal(result["employees"]["e"]["commission"]) == Decimal("0.279875")


def make_seed(monkeypatch, tmp_path, handler=None):
    monkeypatch.setattr(manage, "DIRECTORY", tmp_path)
    args = SimpleNamespace(profile="main", seed=42, batch_size=25, rate=10)
    client = httpx.Client(
        base_url=manage.BASE_URL, transport=httpx.MockTransport(handler or (lambda _r: httpx.Response(200)))
    )
    seed = LoadSeed(config(), MagicMock(), client, args)
    seed.run_id = "nonce"
    return seed


def test_incremental_journal_and_safe_repeat(monkeypatch, tmp_path):
    seed = make_seed(monkeypatch, tmp_path)
    seed.state = {
        "version": plan.VERSION,
        "database": guard.DB,
        "profile": "main",
        "seed": 42,
        "objects": {},
        "steps": [],
        "pending": None,
        "complete": False,
    }
    pending = dict(key="client0", kind="clients", body={"name": "LOAD"}, group="LOAD")
    seed.record(pending, {"clientId": "c", "name": "LOAD"})
    assert "objects" not in json.loads(seed.path.read_text())
    reloaded = LoadSeed(config(), seed.c, seed.http, seed.args)
    assert reloaded.state["objects"]["client0"]["id"] == "c"
    reloaded.request = MagicMock(side_effect=AssertionError("No duplicate POST"))
    reloaded.create("client0", "clients", {"name": "LOAD"})
    reloaded.request.assert_not_called()
    reloaded.args.seed = 43
    with pytest.raises(RuntimeError, match="conflict"):
        LoadSeed(config(), seed.c, seed.http, reloaded.args)


def test_uncertain_catalog_post_recovered(monkeypatch, tmp_path):
    seed = make_seed(monkeypatch, tmp_path)
    seed.state = dict(
        objects={},
        pending=dict(
            key="client0", kind="clients", body={"name": "LOAD"}, path="/protected/clients/create", group="LOAD"
        ),
        steps=[],
        complete=False,
    )
    seed.c.execute.return_value.fetchall.return_value = [("c",)]
    seed.request = MagicMock(return_value={"clientId": "c", "name": "LOAD"})
    seed.recover_pending()
    assert seed.state["pending"] is None
    assert seed.state["objects"]["client0"]["id"] == "c"
    assert seed.request.call_args.args[0] == "GET"


def test_uncertain_mutation_readback_recovers(monkeypatch, tmp_path):
    seed = make_seed(monkeypatch, tmp_path)
    seed.state = dict(
        objects={"client0": dict(id="c", kind="clients", saved={"name": "OLD"})},
        pending=dict(
            key="client0", step="rename", path="/protected/clients/c", desired={"name": "NEW"}, before={"name": "OLD"}
        ),
        steps=[],
        complete=False,
    )
    seed.request = MagicMock(return_value={"name": "NEW"})
    seed.recover_pending()
    assert seed.state["objects"]["client0"]["saved"]["name"] == "NEW"
    assert seed.state["steps"] == ["rename"]
    assert json.loads((seed.objects_dir / "client0.json").read_text())["object"]["saved"]["name"] == "NEW"


@pytest.mark.parametrize("corruption", [None, "duplicate", "total", "order", "missing"])
def test_pagination_checks_all_pages(monkeypatch, tmp_path, corruption):
    expected = [str(n) for n in range(125)]

    def handler(request):
        offset = int(request.url.params["offset"])
        page = expected[offset : offset + 50]
        if offset == 50 and corruption:
            if corruption == "duplicate":
                page[0] = "0"
            if corruption == "missing":
                page = page[1:]
            if corruption == "order":
                page.reverse()
        return httpx.Response(
            200,
            headers={"X-Load-Run": "nonce"},
            json={
                "total": 124 if corruption == "total" else 125,
                "data": {"deliveries": [{"pointId": p} for p in page]},
            },
        )

    seed = make_seed(monkeypatch, tmp_path, handler)
    if corruption:
        with pytest.raises(RuntimeError, match="expected=.*actual="):
            pages(seed, "/protected/client-delivery-history", "deliveries", expected, {})
    else:
        assert len(pages(seed, "/protected/client-delivery-history", "deliveries", expected, {})) == 125


def test_statistics_counts_errors_and_nearest_rank():
    samples = [(float(n), "HTTP_500" if n == 10 else None) for n in range(1, 21)]
    result = statistics_for(samples, 2)
    assert result == dict(
        requests=20,
        successful=19,
        errors={"HTTP_500": 1},
        min_ms=1,
        p50_ms=10.5,
        p95_ms=19,
        max_ms=20,
        requests_per_second=10,
        elapsed_seconds=2,
    )


def test_diagnostics_include_identifier_expected_actual():
    with pytest.raises(RuntimeError, match="doc-id/total: expected=.*actual="):
        equal("doc-id", "total", Decimal("1"), Decimal("2"))


def test_api_statement_checks_the_exact_cursor_before_write():
    conn = MagicMock()
    probe = conn.connection.cursor.return_value.__enter__.return_value
    probe.fetchone.side_effect = [identity(), (True,)]
    probe.fetchall.return_value = [("secret-marker",)]
    guard.statement_guard(config())(conn, None, "INSERT INTO clients VALUES (...) ", None, None, False)
    assert [call.args[0] for call in probe.execute.call_args_list] == [guard.IDENTITY, guard.TOKEN, guard.READ_ONLY]
    row = identity()
    row[0] = "mountain_fairytale_qa"
    probe.fetchone.side_effect = [row, (True,)]
    with pytest.raises(RuntimeError, match="mismatch"):
        guard.statement_guard(config())(conn, None, "INSERT", None, None, False)


def test_complete_repeat_is_readonly(monkeypatch, tmp_path):
    seed = make_seed(monkeypatch, tmp_path)
    seed.state = dict(complete=True, pending=None, objects={}, steps=[])
    seed.guard = MagicMock()
    seed.request = MagicMock(side_effect=AssertionError("business HTTP forbidden"))
    seed.run()
    seed.request.assert_not_called()


def test_wrong_generation_rejected(monkeypatch, tmp_path):
    seed = make_seed(monkeypatch, tmp_path)
    seed.state = dict(
        version=plan.VERSION,
        database=guard.DB,
        profile="main",
        seed=42,
        complete=False,
        pending=None,
        objects={},
        steps=[],
    )
    seed.persist()
    with pytest.raises(RuntimeError, match="generation"):
        LoadSeed(config() | {"LOAD_MARKER": "different-generation"}, seed.c, seed.http, seed.args)


def test_reset_confirmation_and_sessions_refuse_before_writes(monkeypatch, tmp_path):
    monkeypatch.setattr(manage, "DIRECTORY", tmp_path)
    monkeypatch.setattr(manage, "STATE", tmp_path / "process.json")
    c = MagicMock()
    monkeypatch.setattr(manage, "connect", lambda _v: nullcontext(c))
    monkeypatch.setattr(manage, "verify", MagicMock())
    with pytest.raises(RuntimeError, match="confirm"):
        manage.reset(config(), "mountain_fairytale_qa")
    c.execute.assert_not_called()
    c.execute.return_value.fetchone.return_value = (1,)
    with pytest.raises(RuntimeError, match="sessions"):
        manage.reset(config(), guard.DB)
    assert all("TRUNCATE" not in str(call.args[0]) for call in c.execute.call_args_list)


@pytest.mark.parametrize("has_error", [False, True])
def test_benchmark_real_http_sampling_and_error_report(monkeypatch, tmp_path, has_error):
    from scripts.load import benchmark as bench

    calls = []

    def handler(request):
        calls.append(request.url.path)
        status = 500 if has_error and len(calls) == 4 else 200
        return httpx.Response(status, json={"data": {}}, headers={"X-Load-Run": "nonce"})

    seed = make_seed(monkeypatch, tmp_path, handler)
    seed.state = dict(complete=True, pending=None)
    seed.guard = MagicMock()
    monkeypatch.setattr(bench, "scenarios", lambda _s: {"clients": ("/protected/clients", {})})
    monkeypatch.setattr(bench, "resources", lambda: None)
    monkeypatch.setattr(bench.time, "sleep", lambda _s: None)
    if has_error:
        with pytest.raises(RuntimeError, match="contains errors"):
            bench.benchmark(seed, 5, 2)
    else:
        bench.benchmark(seed, 5, 2)
    assert len(calls) == 7  # Two warmup requests excluded from measured samples.
    saved = json.loads((tmp_path / "benchmark.json").read_text())
    result = saved["results"]["clients"]
    assert result["requests"] == 5
    assert result["successful"] == (4 if has_error else 5)
    assert result["errors"] == ({"HTTP_500": 1} if has_error else {})
    assert len(list(tmp_path.glob("benchmark-*-c2.json"))) == 1


def test_document_retry_keeps_native_creation_request_id(monkeypatch, tmp_path):
    seed = make_seed(monkeypatch, tmp_path)
    seed.state = dict(objects={}, steps=[], pending=None, complete=False)
    seed.verify_objects = MagicMock()
    sent = []

    def request(_method, _path, body):
        sent.append(body)
        return {"deliveryDocumentId": "doc"}

    seed.request = request
    original_record = seed.record
    seed.record = MagicMock(side_effect=RuntimeError("interrupted after POST"))
    with pytest.raises(RuntimeError, match="interrupted"):
        seed.create("load-v1-main-42-doc0", "delivery-route-sheets", {"points": []})
    seed.record = original_record
    seed.recover_pending()  # Native idempotency permits replay; no blind catalog lookup.
    seed.create("load-v1-main-42-doc0", "delivery-route-sheets", {"points": []})
    assert len(sent) == 2
    assert sent[0]["creationRequestId"] == sent[1]["creationRequestId"]
    assert len(seed.state["objects"]) == 1


@pytest.mark.parametrize("already_created", [False, True])
def test_repair_old_pickup_intent_only_if_database_proves_absence(monkeypatch, tmp_path, already_created):
    from scripts.load import seed as load_seed

    seed = make_seed(monkeypatch, tmp_path)
    prepared = objects()
    key, kind, body = list(plan.documents(prepared, "main", 42))[9]
    body["creationRequestId"] = str(UUID(int=999999))
    for p, point in enumerate(body["points"]):
        point["memo"] = f"LOAD 9/{p}"
    seed.state = dict(
        objects=prepared,
        steps=[],
        complete=False,
        pending=dict(key=key, kind=kind, body=body, path="/protected/pickup-sheets/create", group="LOAD"),
    )
    connection_guard = MagicMock()
    monkeypatch.setattr(load_seed, "verify", connection_guard)
    seed.c.execute.return_value.fetchone.return_value = ("existing",) if already_created else None
    seed.request = MagicMock(side_effect=AssertionError("Recovery must not create business data"))
    if already_created:
        with pytest.raises(RuntimeError, match="already exists"):
            seed.recover_pending()
        assert all(p["memo"] for p in seed.state["pending"]["body"]["points"])
    else:
        seed.recover_pending()
        pending = seed.state["pending"]
        assert all(p["memo"] == "" for p in pending["body"]["points"])
        assert pending["body"]["creationRequestId"] == str(UUID(int=999999))
        saved = json.loads(seed.path.read_text(encoding="utf-8"))["pending"]
        assert saved == pending
    connection_guard.assert_called_once_with(seed.c, seed.v)
    seed.request.assert_not_called()


def test_history_orders_equal_dates_and_creation_times_independently(monkeypatch):
    from scripts.load import verify as verifier

    docs = []
    for n in range(120):
        doc = dict(
            id=str(UUID(int=n + 1)),
            kind="pickup-sheets" if n % 2 else "delivery-route-sheets",
            saved=dict(
                isActive=True,
                plannedDate="2026-06-15",
                createdAt=f"2026-11-10T10:00:0{n % 3}Z",
                points=[
                    dict(
                        pointId=f"p{n}-{p}",
                        position=p,
                        clientId="c",
                        clientName="LOAD Клиент 00000",
                        clientAddress="LOAD Синтетическая улица 00000",
                        phone="00000000",
                        deliveryDetails="",
                    )
                    for p in (2, 0, 1)
                ],
            ),
        )
        docs.append(doc)
    calls = []

    def capture(_seed, path, field, expected_ids, params):
        calls.append((path, list(expected_ids), params))
        pk = "deliveryDocumentId" if field == "documents" else "pointId"
        return [{pk: identity} for identity in expected_ids]

    monkeypatch.setattr(verifier, "pages", capture)
    card = dict(
        name="LOAD Клиент 00000", address="LOAD Синтетическая улица 00000", phone="00000000", deliveryDetails=""
    )
    seed = SimpleNamespace(state={"objects": {"client0": dict(kind="clients", id="c", saved=card)}})
    verifier.history_checks(seed, docs)
    ordered = sorted(docs, key=lambda o: (o["saved"]["createdAt"], o["id"]), reverse=True)
    assert calls[0][1] == [o["id"] for o in ordered]
    assert calls[2][1] == [
        f"p{int(UUID(o['id'])) - 1}-{p}" for o in ordered if o["kind"] == "delivery-route-sheets" for p in (0, 1, 2)
    ]
    assert calls[-1][2]["search"] == "00000000"
