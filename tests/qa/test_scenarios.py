"""Operator simulation in memory: these tests never connect to persistent QA."""

import copy
import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from scripts.qa.scenarios import DATA_TABLES, Checks, Live, Runner, clean, document_sql, expected_plan, finances
from scripts.qa.seed_plan import TABLES, catalogs, clients


def uid():
    return str(uuid4())


class Memory:
    def __init__(self):
        objects, self.cards = {}, {}
        for key, kind, body, group in catalogs():
            identity = uid()
            parts = TABLES[kind][1].split("_")
            pk = parts[0] + "".join(p.title() for p in parts[1:])
            saved = dict(body, **{pk: identity}, isActive=True)
            objects[key] = dict(id=identity, kind=kind, group=group, saved=saved, initial=body)
            self.cards[key] = saved
        self.cards["rep0"]["commissionPercent"] = "7.5"
        for key, kind, body, group in clients(objects):
            identity = uid()
            saved = dict(body, clientId=identity, isActive=True)
            objects[key] = dict(id=identity, kind=kind, group=group, saved=saved, initial=body)
            self.cards[key] = saved
        self.manifest = dict(version="stage2-v1", complete=True, objects=objects)
        self.data = {table: [] for table in DATA_TABLES}
        self.data["clients"] = [dict(client_id=objects["client0"]["id"], name="CORE")]
        self.data["employees"] = [
            dict(employee_id="operator", username="qa_admin", commission_percent=None, is_active=True)
        ]
        self.documents = {}
        self.identity_value = dict(database="memory-qa", markerHash="test-only")
        self.login_count = 0

    def identity(self):
        return self.identity_value

    def guard(self):
        pass

    def login(self):
        self.login_count += 1

    def catalogs(self):
        return copy.deepcopy(self.cards)

    def capture(self):
        return clean(copy.deepcopy(self.data))

    def get(self, path):
        if "/latest-order" in path:
            return None
        return copy.deepcopy(self.documents[path.rsplit("/", 1)[1]])

    def event(self, kind, payload, operation):
        payload["actor_id"] = "operator"
        self.data["events"].append(
            dict(event_id=uid(), event_type=kind, actor_id="operator", operation_id=operation, payload=payload)
        )

    def operate(self, run):
        """Simulate a human save outside Runner; fixed expected totals are asserted separately."""
        identity = run.get("documentId") or uid()
        previous = self.documents.get(identity)
        api = copy.deepcopy(run["plan"])
        api.update(
            deliveryDocumentId=identity,
            revision=previous["revision"] + 1 if previous else 1,
            createdAt="2026-11-07T12:00:00",
            lastOperationId=None,
        )
        for point in api["points"]:
            point.setdefault("pointId", uid())
            for item in point["items"]:
                item.setdefault("itemId", uid())
        self.documents[identity] = api
        if previous:
            old = document_sql(self.data, identity)
            pids = {p["point_id"] for p in old["points"]}
            for table, field, ids in [
                ("delivery_documents", "delivery_document_id", {identity}),
                ("points", "point_id", pids),
                ("delivery_document_items", "point_id", pids),
                ("point_commissions", "point_id", pids),
                ("document_employee_commissions", "delivery_document_id", {identity}),
            ]:
                self.data[table] = [r for r in self.data[table] if r[field] not in ids]
        else:
            old = None
        self.data["delivery_documents"].append(
            dict(
                delivery_document_id=identity,
                revision=api["revision"],
                planned_date=api["plannedDate"],
                is_active=True,
                document_type="pickup_sheet" if run["scenario"] == "QA-004" else "delivery_route_sheet",
                created_at=api["createdAt"],
                driver_id=api.get("driverId"),
                car_id=api.get("carId"),
                start_mileage=api.get("startMileage"),
                end_mileage=api.get("endMileage"),
            )
        )
        operation = uid()
        self.event(
            "UpdateDeliveryDocumentEvent" if previous else "CreateDeliveryDocumentEvent",
            dict(
                delivery_document_id=identity,
                changes={"points": "changed"} if previous else {},
                data=self.data["delivery_documents"][-1],
            ),
            operation,
        )
        expected = run["expected"]
        for point, exp in zip(api["points"], expected["points"], strict=True):
            pid = point["pointId"]
            row = dict(point_id=pid, delivery_document_id=identity)
            for camel, snake in [
                ("clientId", "client_id"),
                ("position", "position"),
                ("isDelivered", "is_delivered"),
                ("nonDeliveryReason", "non_delivery_reason"),
                ("memo", "memo"),
                ("paymentMethodId", "payment_method_id"),
                ("clientName", "snapshot_client_name"),
                ("phone", "snapshot_phone"),
                ("clientAddress", "snapshot_client_address"),
                ("deliveryDetails", "snapshot_delivery_details"),
                ("salesRepresentativeId", "snapshot_sales_representative_id"),
            ]:
                row[snake] = point[camel]
                if run["scenario"] == "QA-004" and snake in {
                    "snapshot_client_name",
                    "snapshot_phone",
                    "snapshot_client_address",
                    "snapshot_delivery_details",
                }:
                    row[snake] = None
            self.data["points"].append(row)
            changes = {}
            if old:
                prior = next(p for p in old["points"] if p["point_id"] == pid)
                changes = {k: dict(old=prior[k], new=v) for k, v in row.items() if prior[k] != v}
            if not old or changes or run["scenario"] == "QA-002" and point is api["points"][0]:
                self.event(
                    "UpdatePointEvent" if old else "CreatePointEvent",
                    dict(point_id=pid, changes=changes, data=row),
                    operation,
                )
            self.data["point_commissions"].append(
                dict(
                    point_id=pid,
                    sales_representative_id=exp["recipient"],
                    commission_percent=exp["rate"],
                    turnover=exp["turnover"],
                    commission_payable=exp["commission"],
                )
            )
            for item in point["items"]:
                row = dict(point_id=pid, item_id=item["itemId"])
                for camel, snake in [
                    ("productId", "product_id"),
                    ("productName", "product_name"),
                    ("quantity", "quantity"),
                    ("price", "price"),
                    ("isFreePrice", "is_free_price"),
                    ("driverNote", "driver_note"),
                ]:
                    row[snake] = item[camel]
                self.data["delivery_document_items"].append(row)
                if not old:
                    self.event("CreateItemEvent", dict(point_id=pid, product_id=row["product_id"], data=row), operation)
                else:
                    prior = next(i for i in old["items"] if i["item_id"] == item["itemId"])
                    changes = {k: dict(old=prior[k], new=v) for k, v in row.items() if prior[k] != v}
                    if changes:
                        self.event(
                            "UpdateItemEvent",
                            dict(point_id=pid, product_id=row["product_id"], changes=changes),
                            operation,
                        )
        for eid, exp in expected["employees"].items():
            self.data["document_employee_commissions"].append(
                dict(
                    delivery_document_id=identity,
                    employee_id=eid,
                    commission_percent=exp["rate"],
                    turnover=exp["turnover"],
                    commission_payable=exp["commission"],
                )
            )
        return identity


@pytest.fixture
def harness(tmp_path):
    live = Memory()
    runner = Runner(live, tmp_path / "journal.json")

    # HTTP history/report doubles deliberately expose amounts independently of document GET.
    def pages(endpoint, field, date):
        rows = []
        for identity, api in live.documents.items():
            if api["plannedDate"] != date:
                continue
            current_run = next(
                r
                for r in reversed(list(runner.cycle()["runs"].values()))
                if r.get("documentId") == identity or r["plan"]["plannedDate"] == date
            )
            exp = current_run["expected"]
            if field == "documents":
                rows.append(dict(deliveryDocumentId=identity, totalAmount=exp["totalAmount"]))
            elif date == "2026-11-08":
                for point, expected in zip(api["points"], exp["points"], strict=True):
                    h = copy.deepcopy(point)
                    # Only fields actually exposed by the real history schema.
                    for key in ("position", "defaultPaymentMethodId", "defaultPaymentMethodName"):
                        h.pop(key, None)
                    h.update(totalAmount=expected["totalAmount"], documentTotalAmount=exp["totalAmount"])
                    for item, amount in zip(h["items"], expected["lineAmounts"], strict=True):
                        item["amount"] = amount
                    rows.append(h)
        return clean(rows)

    runner.pages = pages
    # Exercise sales() itself separately with report fixtures below.
    runner.sales = lambda *_args: None
    return runner, live


def test_prepare_is_read_only_and_persists_unique_run(harness):
    runner, live = harness
    before = copy.deepcopy(live.data)
    run = runner.prepare("QA-001")
    assert run["expected"]["totalAmount"] == "142.50"
    assert run["expected"]["points"][0]["commission"] == "3.9375"
    assert list(run["expected"]["employees"].values())[0]["commission"] == "1.78125"
    assert live.data == before
    assert run["runId"] in run["plan"]["points"][0]["memo"]
    assert "password" not in runner.path.read_text(encoding="utf-8")
    with pytest.raises(RuntimeError, match="already prepared"):
        runner.prepare("QA-001")


def test_full_sequential_cycle_and_pickup_pass(harness):
    runner, live = harness
    expected = [
        ("QA-001", "142.50", "3.9375", "1.78125"),
        ("QA-002", "169.90", "5.9925", "2.12375"),
        ("QA-003", "90.00", "0", "1.125"),
        ("QA-004", "120.00", "0", "1.5"),
    ]
    doc_ids = []
    for scenario, total, rep, employee in expected:
        run = runner.prepare(scenario)
        assert Decimal(run["expected"]["totalAmount"]) == Decimal(total)
        assert Decimal(run["expected"]["points"][0]["commission"]) == Decimal(rep)
        eid = live.cards["employee0"]["employeeId"]
        assert Decimal(run["expected"]["employees"][eid]["commission"]) == Decimal(employee)
        doc_ids.append(live.operate(run))
        assert runner.verify(scenario) == "PASS"
        journal = runner.path.read_bytes()
        data = copy.deepcopy(live.data)
        assert runner.verify(scenario) == "PASS"
        assert runner.path.read_bytes() == journal
        assert live.data == data
    assert len(set(doc_ids[:3])) == 1
    assert doc_ids[3] != doc_ids[0]
    assert runner.verify("QA-001") == "HISTORICAL PASS"
    assert runner.verify("QA-002") == "HISTORICAL PASS"


@pytest.mark.parametrize(
    "mutation", ["commission", "line", "pointUUID", "itemUUID", "audit", "core", "payment", "employee", "duplicate"]
)
def test_corruption_fails(harness, mutation):
    runner, live = harness
    run = runner.prepare("QA-001")
    identity = live.operate(run)
    if mutation == "commission":
        live.data["point_commissions"][0]["commission_payable"] = "3.94"
    elif mutation == "line":
        original_pages = runner.pages

        def bad_pages(endpoint, field, date):
            result = original_pages(endpoint, field, date)
            if field == "deliveries":
                result[0]["items"][0]["amount"] = "39.99"
            return result

        runner.pages = bad_pages
    elif mutation == "pointUUID":
        live.documents[identity]["points"][0]["pointId"] = uid()
    elif mutation == "itemUUID":
        live.documents[identity]["points"][0]["items"][0]["itemId"] = uid()
    elif mutation == "audit":
        live.data["events"] = []
    elif mutation == "core":
        live.data["clients"][0]["name"] = "unexpected"
    elif mutation == "payment":
        live.documents[identity]["points"][0]["paymentMethodId"] = None
    elif mutation == "employee":
        live.data["document_employee_commissions"][0]["commission_payable"] = "1.78"
    else:
        live.operate(run)
        with pytest.raises(RuntimeError, match="Ambiguous"):
            runner.verify("QA-001")
        return
    assert runner.verify("QA-001") == "FAIL"
    assert any(not c["ok"] for c in run["lastVerification"]["checks"])


def test_dependency_identity_resume_and_new_cycles(harness):
    runner, live = harness
    with pytest.raises(RuntimeError, match="QA-002 not verified"):
        runner.prepare("QA-003")
    run = runner.prepare("QA-001")
    live.operate(run)
    assert runner.verify("QA-001") == "PASS"
    resumed = Runner(live, runner.path)
    assert resumed.cycle()["runs"]["QA-001"]["documentId"] == run["documentId"]
    live.identity_value = dict(database="wrong")
    with pytest.raises(RuntimeError, match="identity changed"):
        resumed.cycle()
    new_run = runner.prepare("QA-004", new_cycle=True)
    assert new_run["runId"] != run["runId"]
    assert len(runner.state["cycles"]) == 2
    assert len(live.documents) == 1


def test_interrupted_atomic_prepare_and_verify(harness, monkeypatch):
    runner, live = harness
    run = runner.prepare("QA-001")
    saved = runner.path.read_bytes()
    live.operate(run)

    def interrupted():
        raise OSError("simulated disk interruption")

    monkeypatch.setattr(runner, "persist", interrupted)
    with pytest.raises(OSError, match="interruption"):
        runner.verify("QA-001")
    assert runner.path.read_bytes() == saved
    resumed = Runner(live, runner.path)
    resumed.pages, resumed.sales = runner.pages, runner.sales
    assert resumed.verify("QA-001") == "PASS"


@pytest.mark.parametrize(
    "manifest", [None, {}, dict(version="stage2-v1", complete=False), dict(version="broken", complete=True)]
)
def test_manifest_guard_refuses_invalid(manifest):
    seed = SimpleNamespace(state=manifest, guard=MagicMock())
    with pytest.raises(RuntimeError, match="manifest"):
        Live(seed).guard()


@pytest.mark.parametrize(
    ("key", "field", "value"),
    [("product1", "basePrice", "21"), ("rep0", "commissionPercent", "8"), ("employee0", "commissionPercent", "2")],
)
def test_changed_catalogs_refused(harness, key, field, value):
    _, memory = harness
    memory.cards[key][field] = value
    seed = SimpleNamespace(state=memory.manifest, inventory=lambda: None, verify_objects=lambda: None, c=MagicMock())
    seed.c.execute.return_value.fetchall.return_value = [
        (memory.cards[f"employee{i}"]["employeeId"], "0") for i in (0, 1)
    ]
    live = Live(seed)
    live.get = lambda path: next(
        copy.deepcopy(c) for c in memory.cards.values() if path.rsplit("/", 1)[1] in c.values()
    )
    with pytest.raises(RuntimeError, match="Changed"):
        live.catalogs()


def test_sales_report_checks_independent_lines_and_groups(harness):
    runner, live = harness
    run = runner.prepare("QA-004")
    live.operate(run)
    report = dict(
        totalAmount="120.00",
        totalQuantity=4,
        paymentMethods=[
            dict(
                paymentMethodId=live.cards[f"payment{i}"]["paymentMethodId"],
                products=[dict(productId=live.cards[f"product{i + 1}"]["productId"], quantity=qty, amount=amount)],
            )
            for i, qty, amount in [(0, 1, "20.00"), (1, 2, "60.00"), (2, 1, "40.00")]
        ],
    )
    live.get = lambda _path: report
    checks = Checks()
    Runner.sales(runner, checks, live.capture(), "2026-11-09")
    assert checks.passed
    report["paymentMethods"][1]["products"][0]["amount"] = "59.99"
    checks = Checks()
    Runner.sales(runner, checks, live.capture(), "2026-11-09")
    assert not checks.passed


def test_rounding_is_per_line_and_commissions_exact(harness):
    _, live = harness
    plan = expected_plan("QA-001", live.manifest["objects"], live.cards, "marker")
    plan["points"][0]["items"][0].update(price="1.005", quantity=1)
    plan["points"][0]["items"][1].update(price="1.005", quantity=1)
    expected = finances(plan, live.cards)
    assert expected["points"][0]["totalAmount"] == "2.02"
    assert expected["points"][0]["commission"] == "0.1515"


def test_corrupt_journal_is_retained(tmp_path):
    path = tmp_path / "journal.json"
    path.write_text(json.dumps(dict(schemaVersion=99)), encoding="utf-8")
    with pytest.raises(RuntimeError, match="Invalid scenario"):
        Runner(Memory(), path)
    assert json.loads(path.read_text())["schemaVersion"] == 99


def test_two_explicit_cycles_keep_documents_and_history(harness):
    runner, live = harness
    first = runner.prepare("QA-004")
    first_id = live.operate(first)
    assert runner.verify("QA-004") == "PASS"
    first_cycle = copy.deepcopy(runner.cycle())
    second = runner.prepare("QA-004", new_cycle=True)
    second_id = live.operate(second)
    assert runner.verify("QA-004") == "PASS"
    assert first_id != second_id
    assert len(live.documents) == 2
    assert runner.state["cycles"][0] == first_cycle


def test_explicit_cycle_archives_active_without_overwrite(harness):
    runner, _ = harness
    runner.prepare("QA-001")
    first = copy.deepcopy(runner.cycle())
    runner.prepare("QA-004", new_cycle=True)
    assert runner.state["cycles"][0] == first


def test_interrupted_prepare_retains_existing_journal(harness, monkeypatch):
    runner, live = harness
    runner.prepare("QA-004")
    original = runner.path.read_bytes()
    monkeypatch.setattr(runner, "persist", MagicMock(side_effect=OSError("disk")))
    with pytest.raises(OSError, match="disk"):
        runner.prepare("QA-001")
    assert runner.path.read_bytes() == original
    assert "QA-001" not in Runner(live, runner.path).cycle()["runs"]


def test_network_failure_does_not_publish_result(harness, monkeypatch):
    runner, live = harness
    run = runner.prepare("QA-001")
    live.operate(run)
    original = runner.path.read_bytes()
    monkeypatch.setattr(live, "get", MagicMock(side_effect=TimeoutError))
    with pytest.raises(TimeoutError):
        runner.verify("QA-001")
    assert runner.path.read_bytes() == original


def test_guard_checks_actual_environment_before_login(harness, monkeypatch):
    runner, live = harness
    monkeypatch.setattr(live, "guard", MagicMock(side_effect=RuntimeError("Actual database mismatch")))
    with pytest.raises(RuntimeError, match="database mismatch"):
        runner.prepare("QA-001")
    assert live.login_count == 0
    assert not runner.path.exists()


def test_changed_dependency_cannot_be_prepared(harness):
    runner, live = harness
    run = runner.prepare("QA-001")
    identity = live.operate(run)
    assert runner.verify("QA-001") == "PASS"
    live.documents[identity]["revision"] += 1
    with pytest.raises(RuntimeError, match="Dependency current document differs"):
        runner.prepare("QA-002")


def test_changed_item_identity_on_edit_fails(harness):
    runner, live = harness
    run = runner.prepare("QA-001")
    live.operate(run)
    assert runner.verify("QA-001") == "PASS"
    run = runner.prepare("QA-002")
    identity = live.operate(run)
    live.documents[identity]["points"][0]["items"][0]["itemId"] = uid()
    assert runner.verify("QA-002") == "FAIL"


def test_repeat_verify_detects_duplicate_after_pass(harness):
    runner, live = harness
    run = runner.prepare("QA-001")
    live.operate(run)
    assert runner.verify("QA-001") == "PASS"
    new = copy.deepcopy(run)
    new["documentId"] = None
    live.operate(new)
    with pytest.raises(RuntimeError, match="Ambiguous"):
        runner.verify("QA-001")


def test_failed_delivery_keeps_previous_successful_latest_order(harness):
    runner, live = harness
    plan = expected_plan("QA-001", live.manifest["objects"], live.cards, "previous route")
    previous_id = live.operate(dict(scenario="QA-001", plan=clean(plan), expected=finances(plan, live.cards)))
    previous_point = live.documents[previous_id]["points"][0]["pointId"]
    original_get = live.get
    live.get = lambda path: dict(pointId=previous_point) if path.endswith("/latest-order") else original_get(path)
    for scenario in ("QA-001", "QA-002", "QA-003"):
        run = runner.prepare(scenario)
        live.operate(run)
        assert runner.verify(scenario) == "PASS"


@pytest.mark.parametrize(
    "field", ["snapshot_client_name", "snapshot_phone", "snapshot_client_address", "snapshot_delivery_details"]
)
def test_anonymous_sql_snapshots_must_be_null(harness, field):
    runner, live = harness
    run = runner.prepare("QA-004")
    live.operate(run)
    live.data["points"][0][field] = "leaked client snapshot"
    assert runner.verify("QA-004") == "FAIL"


def test_audit_snapshot_and_actor_corruption_fail(harness):
    runner, live = harness
    run = runner.prepare("QA-001")
    live.operate(run)
    event = next(e for e in live.data["events"] if e["event_type"] == "CreateDeliveryDocumentEvent")
    event["payload"]["data"]["planned_date"] = "2026-01-01"
    event["actor_id"] = "missing-employee"
    assert runner.verify("QA-001") == "FAIL"
