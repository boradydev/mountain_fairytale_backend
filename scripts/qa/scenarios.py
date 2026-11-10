"""Read-only stage-3 operator scenarios; no production financial calculation imports."""

import copy
import hashlib
import json
import tomllib
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import httpx
from psycopg import sql
from psycopg.rows import dict_row

from scripts.qa import manage as q
from scripts.qa.seed import BASE_URL, Seed, exclusive, save
from scripts.qa.seed_plan import TABLES, VERSION, expectations, money


DIRECTORY = q.ROOT / ".codex-tmp" / "qa-scenarios"
JOURNAL = DIRECTORY / "journal.json"
SCENARIOS = ("QA-001", "QA-002", "QA-003", "QA-004")
DEPENDENCIES = {"QA-002": "QA-001", "QA-003": "QA-002"}
DATA_TABLES = sorted(
    {v[0] for v in TABLES.values()}
    | {"points", "delivery_document_items", "point_commissions", "document_employee_commissions", "events"}
)


def now():
    return datetime.now(UTC).isoformat()


def clean(value):
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    if isinstance(value, set):
        return sorted(clean(v) for v in value)
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, (Decimal, UUID)):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def reference_id(value):
    return value.get("id") if isinstance(value, dict) else value


def snapshot(connection):
    result = {}
    with connection.cursor(row_factory=dict_row) as cursor:
        for table in DATA_TABLES:
            # Never read password hashes, even into memory/journal.
            columns = (
                sql.SQL("employee_id,username,commission_percent,is_active") if table == "employees" else sql.SQL("*")
            )
            rows = clean(cursor.execute(sql.SQL("SELECT {} FROM {}").format(columns, sql.Identifier(table))).fetchall())
            result[table] = sorted(rows, key=lambda r: json.dumps(r, sort_keys=True))
    return result


def document_ids(data):
    return [r["delivery_document_id"] for r in data["delivery_documents"]]


def document_sql(data, identity):
    docs = [r for r in data["delivery_documents"] if r["delivery_document_id"] == identity]
    q.require(len(docs) == 1, f"document/{identity}: expected=1 actual={len(docs)}")
    points = sorted([r for r in data["points"] if r["delivery_document_id"] == identity], key=lambda r: r["position"])
    pids = {p["point_id"] for p in points}
    return dict(
        document=docs[0],
        points=points,
        items=[r for r in data["delivery_document_items"] if r["point_id"] in pids],
        commissions=[r for r in data["point_commissions"] if r["point_id"] in pids],
        employees=[r for r in data["document_employee_commissions"] if r["delivery_document_id"] == identity],
    )


def frozen(data, manifest):
    """CORE rows, descendants, exact commissions and their existing audit are immutable."""
    result = {}
    objects = manifest["objects"]
    ids = {o["id"] for o in objects.values() if o["group"] in ("CORE", "SHARED")}
    pids = {p["point_id"] for p in data["points"] if p["delivery_document_id"] in ids}
    ids |= pids
    ids |= {i["item_id"] for i in data["delivery_document_items"] if i["point_id"] in pids}
    for table, rows in data.items():
        if table == "events":
            result[table] = [r for r in rows if r["payload"].get("subject_id") in ids]
        elif table == "points":
            result[table] = [r for r in rows if r["delivery_document_id"] in ids or r.get("client_id") in ids]
        elif table in ("delivery_document_items", "point_commissions"):
            result[table] = [r for r in rows if r["point_id"] in pids]
        elif table == "document_employee_commissions":
            result[table] = [r for r in rows if r["delivery_document_id"] in ids]
        else:
            pk = next(pk for _, (name, pk) in TABLES.items() if name == table)
            result[table] = [
                {k: v for k, v in r.items() if not (table == "cars" and k == "current_mileage")}
                for r in rows
                if r[pk] in ids
            ]
    return result


class Checks:
    def __init__(self):
        self.rows = []

    def equal(self, path, expected, actual):
        if isinstance(expected, Decimal):
            try:
                actual = Decimal(str(actual))
            except Exception:
                pass
        self.rows.append(dict(path=path, expected=clean(expected), actual=clean(actual), ok=expected == actual))

    def subset(self, path, expected, actual):
        for key, value in expected.items():
            target = actual.get(key)
            if isinstance(value, dict) and isinstance(target, dict):
                self.subset(f"{path}/{key}", value, target)
            elif isinstance(value, list) and isinstance(target, list):
                self.equal(f"{path}/{key}/length", len(value), len(target))
                for index, (left, right) in enumerate(zip(value, target, strict=False)):
                    if isinstance(left, dict) and isinstance(right, dict):
                        self.subset(f"{path}/{key}/{index}", left, right)
                    else:
                        self.equal(f"{path}/{key}/{index}", left, right)
            else:
                self.equal(f"{path}/{key}", value, target)

    def exact(self, path, expected, actual):
        if isinstance(expected, dict) and isinstance(actual, dict):
            self.equal(path + "/keys", sorted(expected), sorted(actual))
            for key, value in expected.items():
                self.exact(f"{path}/{key}", value, actual.get(key))
        elif isinstance(expected, list) and isinstance(actual, list):
            self.equal(path + "/count", len(expected), len(actual))
            for index, (left, right) in enumerate(zip(expected, actual, strict=False)):
                label = (
                    next(
                        (
                            left[k]
                            for k in ("event_id", "item_id", "point_id", "delivery_document_id", "client_id")
                            if k in left
                        ),
                        index,
                    )
                    if isinstance(left, dict)
                    else index
                )
                self.exact(f"{path}/{label}", left, right)
        else:
            self.equal(path, expected, actual)

    @property
    def passed(self):
        return all(r["ok"] for r in self.rows)


def expected_plan(scenario, objects, catalogs, marker, previous=None):
    def item(n, qty, price, note=""):
        product = catalogs[f"product{n}"]
        return dict(
            productId=product["productId"],
            productName=product["name"],
            quantity=qty,
            price=Decimal(price),
            isFreePrice=product["isFreePrice"],
            driverNote=note,
        )

    if previous is not None:
        plan = copy.deepcopy(previous)
        plan.pop("revision", None)
        plan.pop("lastOperationId", None)
        if scenario == "QA-002":
            plan["points"][0]["items"][0]["quantity"] = 3
            plan["points"][0]["items"][1]["price"] = Decimal("19.90")
        else:
            plan["points"][0].update(isDelivered=False, nonDeliveryReason="QA-003: клиент отказался")
        return plan
    pickup = scenario == "QA-004"
    plan = dict(plannedDate="2026-11-09" if pickup else "2026-11-08", isActive=True, points=[])
    if not pickup:
        plan.update(
            driverId=objects["driver0"]["id"],
            carId=objects["car0"]["id"],
            startMileage=Decimal(str(catalogs["car0"]["currentMileage"])),
            endMileage=None,
        )
    for index in range(3 if pickup else 2):
        client = None if pickup else catalogs[f"client{21 + index}"]
        payment = (
            catalogs[f"payment{index}"]
            if pickup
            else next(p for p in catalogs.values() if p.get("paymentMethodId") == client["defaultPaymentMethodId"])
        )
        point = dict(
            clientId=client["clientId"] if client else None,
            position=index,
            isDelivered=True,
            nonDeliveryReason="",
            memo=marker if not pickup and index == 0 else "",
            paymentMethodId=payment["paymentMethodId"],
            paymentMethodName=payment["name"],
            salesRepresentativeId=client["salesRepresentativeId"] if client else None,
            clientName=client["name"] if client else "",
            phone=client["phone"] if client else "",
            clientAddress=client["address"] if client else "",
            deliveryDetails=client["deliveryDetails"] if client else "",
        )
        if pickup:
            point.update(
                address="", defaultPaymentMethodId=None, defaultPaymentMethodName=None, salesRepresentativeName=None
            )
            point["items"] = [item(index + 1, 2 if index == 1 else 1, str((index + 2) * 10))]
        else:
            point["items"] = (
                [item(1, 2, "20"), item(8, 1, "12.50", "QA-001: тест свободной цены")]
                if index == 0
                else [item(2, 3, "30")]
            )
        plan["points"].append(point)
    return plan


def finances(plan, catalogs):
    rates = {
        catalogs[f"client{n}"]["clientId"]: (catalogs[f"rep{i}"]["salesRepresentativeId"], rate)
        for n, i, rate in [(21, 0, "7.5"), (22, 1, "0")]
    }
    employee_rates = {
        c["employeeId"]: c["commissionPercent"]
        for c in catalogs.values()
        if c.get("employeeId") and c.get("isActive") and c.get("commissionPercent") is not None
    }
    return expectations(plan, rates, employee_rates)


def verify_document(checks, scenario, run, data, api, history, client_history):
    identity = api["deliveryDocumentId"]
    root = f"{scenario}/{identity}"
    plan, expected = run["plan"], run["expected"]
    # JSON monetary inputs remain Decimal comparisons after journal reload.
    plan = copy.deepcopy(plan)
    for point in plan["points"]:
        for item in point["items"]:
            item["price"] = Decimal(str(item["price"]))
    if "startMileage" in plan:
        plan["startMileage"] = Decimal(str(plan["startMileage"]))
    checks.subset(root + "/api", plan, api)
    stored = document_sql(data, identity)
    doc = stored["document"]
    checks.equal(
        root + "/sql/type", "pickup_sheet" if scenario == "QA-004" else "delivery_route_sheet", doc["document_type"]
    )
    for key in ("revision", "plannedDate", "isActive", "createdAt"):
        snake = {"plannedDate": "planned_date", "isActive": "is_active", "createdAt": "created_at"}.get(key, key)
        checks.equal(root + "/sql/" + key, api[key], doc[snake])
    for camel, snake in [
        ("driverId", "driver_id"),
        ("carId", "car_id"),
        ("startMileage", "start_mileage"),
        ("endMileage", "end_mileage"),
    ]:
        checks.equal(root + "/sql/" + snake, api.get(camel), doc[snake])
    checks.equal(root + "/sql/points/count", len(plan["points"]), len(stored["points"]))
    all_ids = [identity]
    for index, (point, row, exp) in enumerate(zip(api["points"], stored["points"], expected["points"], strict=False)):
        pid = point["pointId"]
        path = root + "/points/" + pid
        all_ids.append(pid)
        for camel, snake in [
            ("pointId", "point_id"),
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
            expected_value = point[camel]
            if scenario == "QA-004" and snake in {
                "snapshot_client_name",
                "snapshot_phone",
                "snapshot_client_address",
                "snapshot_delivery_details",
            }:
                expected_value = None  # API presents absent anonymous SQL snapshots as empty strings.
            checks.equal(path + "/sql/" + snake, expected_value, row[snake])
        rows = {i["item_id"]: i for i in stored["items"] if i["point_id"] == pid}
        checks.equal(path + "/sql/items/count", len(point["items"]), len(rows))
        for item in point["items"]:
            iid = item["itemId"]
            all_ids.append(iid)
            target = rows.get(iid, {})
            for camel, snake in [
                ("productId", "product_id"),
                ("productName", "product_name"),
                ("quantity", "quantity"),
                ("price", "price"),
                ("isFreePrice", "is_free_price"),
                ("driverNote", "driver_note"),
            ]:
                value = Decimal(str(item[camel])) if camel == "price" else item[camel]
                checks.equal(path + "/items/" + iid + "/sql/" + snake, value, target.get(snake))
        commissions = [c for c in stored["commissions"] if c["point_id"] == pid]
        checks.equal(path + "/commission/count", 1, len(commissions))
        if commissions:
            for field, key in [
                ("sales_representative_id", "recipient"),
                ("commission_percent", "rate"),
                ("turnover", "turnover"),
                ("commission_payable", "commission"),
            ]:
                value = exp[key] if key == "recipient" else Decimal(exp[key])
                checks.equal(path + "/commission/" + field, value, commissions[0][field])
        entries = [h for h in client_history if h["pointId"] == pid]
        checks.equal(path + "/client-history/count", 0 if scenario == "QA-004" else 1, len(entries))
        if entries:
            h = entries[0]
            checks.equal(path + "/client-history/amount", Decimal(exp["totalAmount"]), h["totalAmount"])
            checks.equal(
                path + "/client-history/documentAmount", Decimal(expected["totalAmount"]), h["documentTotalAmount"]
            )
            checks.subset(
                path + "/client-history",
                {
                    k: v
                    for k, v in plan["points"][index].items()
                    if k
                    in {
                        "pointId",
                        "clientId",
                        "clientName",
                        "phone",
                        "clientAddress",
                        "deliveryDetails",
                        "salesRepresentativeId",
                        "isDelivered",
                        "nonDeliveryReason",
                        "memo",
                        "paymentMethodId",
                        "items",
                    }
                },
                h,
            )
            hitems = {i["itemId"]: i for i in h["items"]}
            checks.equal(path + "/client-history/items", set(rows), set(hitems))
            for item, amount in zip(point["items"], exp["lineAmounts"], strict=False):
                checks.equal(
                    path + "/items/" + item["itemId"] + "/amount",
                    Decimal(amount),
                    hitems.get(item["itemId"], {}).get("amount"),
                )
    checks.equal(root + "/uniqueUUIDs", len(all_ids), len(set(all_ids)))
    if scenario == "QA-004":
        checks.equal(
            root + "/client-history/documentEntries",
            [],
            [h.get("pointId") for h in client_history if h.get("deliveryDocumentId") == identity],
        )
    employees = {e["employee_id"]: e for e in stored["employees"]}
    checks.equal(root + "/employees/recipients", sorted(expected["employees"]), sorted(employees))
    for eid, exp in expected["employees"].items():
        for key, field in [
            ("rate", "commission_percent"),
            ("turnover", "turnover"),
            ("commission", "commission_payable"),
        ]:
            checks.equal(root + "/employees/" + eid + "/" + field, Decimal(exp[key]), employees.get(eid, {}).get(field))
    matches = [h for h in history if h["deliveryDocumentId"] == identity]
    checks.equal(root + "/history/count", 1, len(matches))
    if matches:
        checks.equal(root + "/history/totalAmount", Decimal(expected["totalAmount"]), matches[0]["totalAmount"])
    revision = run.get("beforeDocument", {}).get("revision", 0) + 1
    checks.equal(root + "/revision", revision, api["revision"])
    before_events = {e["event_id"] for e in run["before"]["events"]}
    events = [e for e in data["events"] if e["event_id"] not in before_events]
    event_type = "CreateDeliveryDocumentEvent" if scenario in ("QA-001", "QA-004") else "UpdateDeliveryDocumentEvent"
    matches = [
        e for e in events if e["event_type"] == event_type and e["payload"].get("delivery_document_id") == identity
    ]
    checks.equal(root + "/audit/" + event_type + "/count", 1, len(matches))
    if matches:
        operation = matches[0]["operation_id"]
        group = [e for e in events if e["operation_id"] == operation]
        if scenario in ("QA-001", "QA-004"):
            audit_data = matches[0]["payload"].get("data", {})
            for field in ("planned_date", "is_active", "driver_id", "car_id", "start_mileage", "end_mileage"):
                value = doc[field]
                if field in ("start_mileage", "end_mileage") and value is not None:
                    value = Decimal(str(value))
                checks.equal(root + "/audit/document/" + field, value, reference_id(audit_data.get(field)))
            for point in stored["points"]:
                pid = point["point_id"]
                point_events = [
                    e for e in group if e["event_type"] == "CreatePointEvent" and e["payload"].get("point_id") == pid
                ]
                if point_events:
                    audit_data = point_events[0]["payload"].get("data", {})
                    for field in (
                        "point_id",
                        "client_id",
                        "position",
                        "snapshot_client_name",
                        "snapshot_phone",
                        "snapshot_client_address",
                        "snapshot_delivery_details",
                        "snapshot_sales_representative_id",
                        "payment_method_id",
                        "is_delivered",
                        "non_delivery_reason",
                        "memo",
                    ):
                        checks.equal(
                            root + "/audit/points/" + pid + "/" + field,
                            point[field],
                            reference_id(audit_data.get(field)),
                        )
        checks.equal(root + "/audit/actor", 1, len({e["actor_id"] for e in group}))
        employee_ids = {e["employee_id"] for e in data["employees"]}
        for event in group:
            path = root + "/audit/" + event["event_id"]
            checks.equal(path + "/knownActor", True, event["actor_id"] in employee_ids)
            checks.equal(path + "/payloadActor", event["actor_id"], event["payload"].get("actor_id"))
        checks.equal(
            root + "/audit/deletions", [], [e["event_type"] for e in group if e["event_type"].startswith("Delete")]
        )
        checks.equal(
            root + "/audit/nonempty",
            True,
            bool(matches[0]["payload"].get("data") or matches[0]["payload"].get("changes")),
        )
        for point in api["points"][:1] if scenario in ("QA-002", "QA-003") else api["points"]:
            kind = (
                "UpdatePointEvent"
                if scenario == "QA-003"
                else "CreatePointEvent"
                if scenario in ("QA-001", "QA-004")
                else "UpdateItemEvent"
            )
            checks.equal(
                root + "/audit/" + point["pointId"] + "/" + kind,
                True,
                any(e["event_type"] == kind and e["payload"].get("point_id") == point["pointId"] for e in group),
            )
        for item in stored["items"]:
            iid, pid = item["item_id"], item["point_id"]
            if scenario in ("QA-001", "QA-004"):
                item_events = [
                    e
                    for e in group
                    if e["event_type"] == "CreateItemEvent" and e["payload"].get("data", {}).get("item_id") == iid
                ]
                checks.equal(root + "/audit/items/" + iid + "/create/count", 1, len(item_events))
                if item_events:
                    audit_data = item_events[0]["payload"]["data"]
                    for field, value in item.items():
                        if field == "point_id":
                            continue
                        expected_value = Decimal(str(value)) if field == "price" else value
                        checks.equal(
                            root + "/audit/items/" + iid + "/" + field,
                            expected_value,
                            reference_id(audit_data.get(field)),
                        )
            elif scenario == "QA-002":
                old = next((i for i in run["before"]["delivery_document_items"] if i["item_id"] == iid), {})
                for field in ("quantity", "price"):
                    if old.get(field) == item[field]:
                        continue
                    item_events = [
                        e
                        for e in group
                        if e["event_type"] == "UpdateItemEvent"
                        and e["payload"].get("point_id") == pid
                        and e["payload"].get("changes", {}).get(field) is not None
                        and reference_id(e["payload"].get("product_id")) == item["product_id"]
                    ]
                    checks.equal(root + "/audit/items/" + iid + "/" + field + "/count", 1, len(item_events))
                    if item_events:
                        changes = item_events[0]["payload"]["changes"][field]
                        checks.equal(
                            root + "/audit/items/" + iid + "/" + field + "/old",
                            Decimal(str(old[field])),
                            changes["old"],
                        )
                        checks.equal(
                            root + "/audit/items/" + iid + "/" + field + "/new",
                            Decimal(str(item[field])),
                            changes["new"],
                        )
        if scenario == "QA-003":
            pid = api["points"][0]["pointId"]
            point_events = [
                e for e in group if e["event_type"] == "UpdatePointEvent" and e["payload"].get("point_id") == pid
            ]
            for field, old, new in [
                ("is_delivered", True, False),
                ("non_delivery_reason", "", "QA-003: клиент отказался"),
            ]:
                changes = point_events[0]["payload"].get("changes", {}).get(field, {}) if point_events else {}
                checks.equal(root + "/audit/" + field + "/old", old, changes.get("old"))
                checks.equal(root + "/audit/" + field + "/new", new, changes.get("new"))
    warehouse = {}
    for point in api["points"]:
        for item in point["items"]:
            if not item["isFreePrice"]:
                pid = item["productId"]
                warehouse[pid] = warehouse.get(pid, 0) + item["quantity"]
    checks.equal(root + "/warehouse/sourceQuantities", expected["warehouse"], warehouse)
    return stored


class Live:
    def __init__(self, seed):
        self.seed = seed
        self.manifest = seed.state

    def guard(self):
        self.seed.guard()
        m = self.manifest
        q.require(
            m and m.get("version") == VERSION and m.get("complete") and not m.get("pending"),
            "Missing/incomplete stage2-v1 manifest",
        )
        q.require(
            len(m["objects"]) == 64 and len({o["id"] for o in m["objects"].values()}) == 64, "Corrupt stage2-v1 objects"
        )
        expected_keys = {
            f"{prefix}{i}"
            for prefix, count in [
                ("payment", 3),
                ("rep", 3),
                ("employee", 3),
                ("driver", 2),
                ("car", 2),
                ("product", 10),
                ("client", 30),
                ("route", 8),
                ("pickup", 3),
            ]
            for i in range(count)
        }
        q.require(set(m["objects"]) == expected_keys, "Corrupt stage2-v1 membership")
        for key, obj in m["objects"].items():
            q.require(
                obj.get("kind") in TABLES and obj.get("group") in ("CORE", "MANUAL", "SHARED"),
                f"Corrupt manifest {key}",
            )
            q.require(bool(obj.get("initial")) and bool(obj.get("saved")), f"Missing manifest snapshot {key}")

    def login(self):
        self.seed.login()

    def get(self, path):
        return self.seed.request("GET", path)

    def capture(self):
        self.seed.c.rollback()
        self.seed.c.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        q.verify(self.seed.c, self.seed.v)
        return snapshot(self.seed.c)

    def identity(self):
        return dict(database=q.DB, host=q.HOST, port=q.PORT, role=q.ROLE, markerHash=digest(self.seed.v["QA_MARKER"]))

    def catalogs(self):
        self.seed.inventory()
        self.seed.verify_objects()
        result = {
            key: self.get(f"/protected/{obj['kind']}/{obj['id']}")
            for key, obj in self.manifest["objects"].items()
            if not obj.get("expected")
        }
        employees = self.seed.c.execute(
            "SELECT employee_id,commission_percent FROM employees WHERE is_active AND commission_percent IS NOT NULL"
        ).fetchall()
        q.require(
            {str(e) for e, _ in employees} == {result[f"employee{i}"]["employeeId"] for i in (0, 1)},
            "Changed employee recipient set",
        )
        for n, price in [(1, "20"), (2, "30"), (3, "40"), (8, "0")]:
            p = result[f"product{n}"]
            q.require(
                p["isActive"] and p["isFreePrice"] == (n == 8) and Decimal(str(p["basePrice"])) == Decimal(price),
                f"Changed product{n} price/free-price/active",
            )
        for n, rate in [(0, "7.5"), (1, "0")]:
            rep = result[f"rep{n}"]
            q.require(
                rep["isActive"] and Decimal(str(rep["commissionPercent"])) == Decimal(rate),
                f"Changed rep{n} rate/active",
            )
            client = result[f"client{21 + n}"]
            q.require(
                client["isActive"] and client["salesRepresentativeId"] == rep["salesRepresentativeId"],
                f"Changed client{21 + n} assignment/active",
            )
            q.require(
                client["defaultPaymentMethodId"] in {result[f"payment{i}"]["paymentMethodId"] for i in range(3)},
                "Unexpected client payment",
            )
        q.require(Decimal(str(result["employee0"]["commissionPercent"])) == Decimal("1.25"), "Changed employee0 rate")
        q.require(Decimal(str(result["employee1"]["commissionPercent"])) == 0, "Changed employee1 rate")
        for key in ["driver0", "car0", "payment0", "payment1", "payment2"]:
            q.require(result[key]["isActive"], f"Inactive {key}")
        return result


class Runner:
    def __init__(self, live, path=JOURNAL):
        self.live, self.path = live, path
        self.state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else dict(schemaVersion=1, cycles=[])
        q.require(
            self.state.get("schemaVersion") == 1 and isinstance(self.state.get("cycles"), list),
            "Invalid scenario journal; retained",
        )

    def persist(self):
        save(self.path, clean(self.state))

    def cycle(self, create=False):
        if not self.state["cycles"]:
            q.require(create, "No scenario cycle; run scenario-prepare QA-001 or QA-004")
            self.state["cycles"].append(dict(id=str(uuid4()), identity=self.live.identity(), runs={}, createdAt=now()))
        cycle = self.state["cycles"][-1]
        q.require(
            cycle["identity"] == self.live.identity(),
            "QA identity changed; use explicit --new-cycle (old history retained)",
        )
        return cycle

    def prepare(self, scenario, new_cycle=False):
        self.live.guard()
        if new_cycle:
            q.require(scenario in ("QA-001", "QA-004"), "New cycle must start at QA-001 or QA-004")
            # Explicit new cycle archives even unfinished runs, without modifying any old record/document.
            self.state["cycles"].append(dict(id=str(uuid4()), identity=self.live.identity(), runs={}, createdAt=now()))
        cycle = self.cycle(create=True)
        q.require(scenario not in cycle["runs"], "Scenario already prepared; use verify/status. No journal overwritten")
        dependency = DEPENDENCIES.get(scenario)
        previous = cycle["runs"].get(dependency) if dependency else None
        q.require(not dependency or previous and previous["status"] == "PASS", f"BLOCKED: {dependency} not verified")
        self.live.login()
        catalogs = self.live.catalogs()
        before = self.live.capture()
        seed_checks = Checks()
        for key, obj in self.live.manifest["objects"].items():
            if not obj.get("expected"):
                continue
            stored = document_sql(before, obj["id"])
            for point, exp in zip(stored["points"], obj["expected"]["points"], strict=True):
                rows = [r for r in stored["commissions"] if r["point_id"] == point["point_id"]]
                seed_checks.equal(f"CORE/{key}/{point['point_id']}/commission/count", 1, len(rows))
                if rows:
                    for field, target in [
                        ("sales_representative_id", "recipient"),
                        ("commission_percent", "rate"),
                        ("turnover", "turnover"),
                        ("commission_payable", "commission"),
                    ]:
                        value = exp[target] if target == "recipient" else Decimal(exp[target])
                        seed_checks.equal(f"CORE/{key}/{point['point_id']}/{field}", value, rows[0][field])
            rows = {r["employee_id"]: r for r in stored["employees"]}
            seed_checks.equal(f"CORE/{key}/employees", sorted(obj["expected"]["employees"]), sorted(rows))
            for eid, exp in obj["expected"]["employees"].items():
                for field, target in [
                    ("commission_percent", "rate"),
                    ("turnover", "turnover"),
                    ("commission_payable", "commission"),
                ]:
                    seed_checks.equal(f"CORE/{key}/{eid}/{field}", Decimal(exp[target]), rows.get(eid, {}).get(field))
        q.require(
            seed_checks.passed,
            "Seed financial integrity FAIL: "
            + json.dumps([r for r in seed_checks.rows if not r["ok"]], ensure_ascii=False),
        )
        previous_api = None
        if previous:
            previous_api = self.live.get(f"/protected/delivery-route-sheets/{previous['documentId']}")
            q.require(
                previous_api == previous["confirmedDocument"],
                "Dependency current document differs from its PASS; inspect before continuing",
            )
        run_id = str(uuid4())
        marker = f"QA-001 run={run_id}"
        plan = expected_plan(scenario, self.live.manifest["objects"], catalogs, marker, previous_api)
        run = dict(
            runId=run_id,
            scenario=scenario,
            status="READY",
            preparedAt=now(),
            marker=marker,
            before=before,
            core=frozen(before, self.live.manifest),
            catalogs=catalogs,
            manifestHash=digest(self.live.manifest),
            plan=clean(plan),
            expected=finances(plan, catalogs),
            beforeDocument=previous_api or {},
            documentId=previous["documentId"] if previous else None,
        )
        cycle["runs"][scenario] = run
        self.persist()  # One atomic commit; interrupted preparation never publishes half a baseline.
        self.instructions(run)
        return run

    def instructions(self, run):
        print(f"{run['scenario']} READY run={run['runId']}; API {BASE_URL}; cycle={self.cycle()['id']}")
        print(
            "Flutter: docs/qa/scenarios/"
            + {
                "QA-001": "QA-001-create-delivery.md",
                "QA-002": "QA-002-edit-delivery.md",
                "QA-003": "QA-003-failed-delivery.md",
                "QA-004": "QA-004-anonymous-pickup.md",
            }[run["scenario"]]
        )
        if run["documentId"]:
            print("Open existing document UUID:", run["documentId"])
        if run["scenario"] == "QA-001":
            cards = run["catalogs"]
            print("Driver:", cards["driver0"]["name"], "Car:", cards["car0"]["model"], cards["car0"]["number"])
            print("Use start mileage from plan; leave end mileage blank. Do not modify catalogs.")
        print("Enter exactly this plan (do not enter IDs manually):")
        print(json.dumps(run["plan"], ensure_ascii=False, indent=2))
        print("Expected amounts/commissions:", json.dumps(run["expected"], ensure_ascii=False))
        print("Verify UI visually, save once, then: .\\scripts\\qa\\qa.ps1 scenario-verify", run["scenario"])

    def verify(self, scenario):
        self.live.guard()
        cycle = self.cycle()
        q.require(scenario in cycle["runs"], "Scenario NOT PREPARED")
        run = cycle["runs"][scenario]
        q.require(digest(self.live.manifest) == run["manifestHash"], "Seed manifest changed; inspect journal")
        self.live.login()  # May append EmployeeLoginEvent; excluded from business checks explicitly.
        data = self.live.capture()
        checks = Checks()
        checks.exact(scenario + "/CORE", run["core"], frozen(data, self.live.manifest))
        identity = run["documentId"]
        if scenario in ("QA-001", "QA-004"):
            kind = "pickup_sheet" if scenario == "QA-004" else "delivery_route_sheet"
            new = set(document_ids(data)) - set(document_ids(run["before"]))
            candidates = [
                d["delivery_document_id"]
                for d in data["delivery_documents"]
                if d["delivery_document_id"] in new and d["document_type"] == kind
            ]
            q.require(
                len(candidates) == 1,
                f"Ambiguous/missing new document: expected=1 actual={len(candidates)} UUIDs={candidates}",
            )
        if not identity:
            new = set(document_ids(data)) - set(document_ids(run["before"]))
            kind = "pickup_sheet" if scenario == "QA-004" else "delivery_route_sheet"
            candidates = [
                d["delivery_document_id"]
                for d in data["delivery_documents"]
                if d["delivery_document_id"] in new and d["document_type"] == kind
            ]
            q.require(
                len(candidates) == 1,
                f"Ambiguous/missing new document: expected=1 actual={len(candidates)} UUIDs={candidates}",
            )
            identity = candidates[0]
        kind = "pickup-sheets" if scenario == "QA-004" else "delivery-route-sheets"
        api = self.live.get(f"/protected/{kind}/{identity}")
        if scenario == "QA-001":
            checks.equal(
                scenario + "/" + identity + "/run-marker",
                run["marker"],
                api["points"][0]["memo"] if api["points"] else None,
            )
        # A historical PASS must never be advertised as verification of a later revision.
        if run.get("confirmedDocument") and api != run["confirmedDocument"]:
            successors = [
                r
                for s, r in cycle["runs"].items()
                if s > scenario and s != "QA-004" and r.get("documentId") == identity
            ]
            if successors:
                print(
                    f"{scenario} HISTORICAL PASS; current document changed by later scenario; current PASS not asserted"
                )
                return "HISTORICAL PASS"
        date = run["plan"]["plannedDate"]
        history = self.pages("/protected/delivery-history", "documents", date)
        clients = self.pages("/protected/client-delivery-history", "deliveries", date)
        stored = verify_document(checks, scenario, run, data, api, history, clients)
        if run.get("beforeDocument"):
            baseline = document_sql(run["before"], identity)
            allowed = {"quantity", "price"} if scenario == "QA-002" else set()
            for table in ("items", "points"):
                left = copy.deepcopy(baseline[table])
                right = copy.deepcopy(stored[table])
                if table == "items":
                    for rows in (left, right):
                        for row in rows:
                            for field in allowed:
                                row.pop(field, None)
                else:
                    for rows in (left, right):
                        for row in rows:
                            for field in ("is_delivered", "non_delivery_reason") if scenario == "QA-003" else ():
                                row.pop(field, None)
                checks.equal(scenario + "/preserved/" + table, left, right)
        if scenario == "QA-003":
            cid = run["catalogs"]["client21"]["clientId"]
            latest = self.live.get(f"/protected/clients/{cid}/latest-order")
            eligible = [
                p
                for p in data["points"]
                if p["client_id"] == cid
                and p["is_delivered"]
                and any(i["point_id"] == p["point_id"] for i in data["delivery_document_items"])
                and any(
                    d["delivery_document_id"] == p["delivery_document_id"]
                    and d["is_active"]
                    and d["document_type"] == "delivery_route_sheet"
                    for d in data["delivery_documents"]
                )
            ]
            dates = {d["delivery_document_id"]: d["created_at"] for d in data["delivery_documents"]}
            eligible.sort(
                key=lambda p: (dates[p["delivery_document_id"]], p["delivery_document_id"], p["point_id"]), reverse=True
            )
            checks.equal(
                scenario + "/latest-order/pointId",
                eligible[0]["point_id"] if eligible else None,
                latest["pointId"] if latest else None,
            )
        self.sales(checks, data, date)
        # Detect concurrent API/UI writes instead of combining two different states into PASS.
        after = self.live.capture()
        checks.equal(
            scenario + "/stableRead",
            {k: v for k, v in data.items() if k != "events"},
            {k: v for k, v in after.items() if k != "events"},
        )
        result = "PASS" if checks.passed else "FAIL"
        verification = clean(dict(at=now(), status=result, checks=checks.rows, document=api, sql=stored))
        if (
            run.get("confirmedDocument") == api
            and run.get("lastVerification", {}).get("status") == result
            and result == "PASS"
        ):
            print(scenario, "PASS (same confirmed state; journal unchanged)")
            return result
        run.update(documentId=identity, status=result, lastVerification=verification)
        if result == "PASS":
            run.setdefault("confirmedDocument", api)
            run.setdefault("confirmedAt", now())
        self.persist()  # Previous complete result survives interruption before atomic replacement.
        print(scenario, result)
        for row in checks.rows:
            if not row["ok"]:
                print(f"{row['path']}: expected={row['expected']} actual={row['actual']}")
        return result

    def pages(self, endpoint, field, date):
        result = []
        for offset in range(0, 100000, 100):
            page = self.live.get(
                f"{endpoint}?date_from={date}&date_to={date}&limit=100&offset={offset}&include_cancelled=true"
            )[field]
            result.extend(page)
            if len(page) < 100:
                return result
        raise RuntimeError("History pagination safety limit; no PASS")

    def sales(self, checks, data, date):
        amounts, quantity, groups = Decimal(0), 0, {}
        docs = {
            d["delivery_document_id"]
            for d in data["delivery_documents"]
            if d["is_active"] and d["planned_date"] == date
        }
        for point in data["points"]:
            if point["delivery_document_id"] not in docs or not point["is_delivered"]:
                continue
            for item in data["delivery_document_items"]:
                if item["point_id"] != point["point_id"] or item["is_free_price"] and Decimal(item["price"]) == 0:
                    continue
                amount = money(Decimal(item["price"]) * item["quantity"])
                amounts += amount
                quantity += item["quantity"]
                key = (point["payment_method_id"], item["product_id"])
                group = groups.setdefault(key, [0, Decimal(0)])
                group[0] += item["quantity"]
                group[1] += amount
        api = self.live.get(f"/protected/sales-report?date_from={date}&date_to={date}")
        checks.equal("sales-report/" + date + "/totalAmount", amounts, api["totalAmount"])
        checks.equal("sales-report/" + date + "/totalQuantity", quantity, api["totalQuantity"])
        actual = {}
        product_rows = 0
        for method in api["paymentMethods"]:
            for product in method["products"]:
                product_rows += 1
                actual[(method["paymentMethodId"], product["productId"])] = (
                    product["quantity"],
                    Decimal(product["amount"]),
                )
        checks.equal("sales-report/products", sorted(str(k) for k in groups), sorted(str(k) for k in actual))
        checks.equal("sales-report/productRows", len(actual), product_rows)
        for key, (qty, amount) in groups.items():
            value = actual.get(key, (None, None))
            checks.equal(f"sales-report/{key}/quantity", qty, value[0])
            checks.equal(f"sales-report/{key}/amount", amount, value[1])

    def status(self):
        if not self.state["cycles"]:
            for scenario in SCENARIOS:
                print(scenario, "NOT PREPARED", "dependency=" + DEPENDENCIES.get(scenario, "none"))
            return
        cycle = self.cycle()
        print("Cycle:", cycle["id"], "retained cycles:", len(self.state["cycles"]))
        for scenario in SCENARIOS:
            run = cycle["runs"].get(scenario)
            dep = DEPENDENCIES.get(scenario)
            status = (
                run["status"]
                if run
                else f"BLOCKED: {dep} not verified"
                if dep and cycle["runs"].get(dep, {}).get("status") != "PASS"
                else "NOT PREPARED"
            )
            if (
                run
                and run.get("confirmedDocument")
                and any(
                    r.get("documentId") == run.get("documentId")
                    for s, r in cycle["runs"].items()
                    if scenario < s < "QA-004"
                )
            ):
                status += " (historical; later step prepared; verify checks current state)"
            print(scenario, status, "run=" + run["runId"] if run else "", "dependency=" + (dep or "none"))
            if run and run.get("errors"):
                print("  Last read failure:", run["errors"][-1])


def command(v, action, scenario=None, new_cycle=False):
    q.require(action == "scenario-status" or scenario in SCENARIOS, "Specify QA-001, QA-002, QA-003 or QA-004")
    with (
        exclusive(),
        exclusive(DIRECTORY),
        q.connect(v) as connection,
        httpx.Client(base_url=BASE_URL, trust_env=False, timeout=30) as client,
    ):
        policy = tomllib.loads((q.ROOT / "client_compatibility.toml").read_text(encoding="utf-8"))
        client.headers["X-Client-Version"] = policy["flutter"]["min_version"]
        live = Live(Seed(v, connection, client))
        connection.rollback()
        connection.read_only = True
        runner = Runner(live)
        if action == "scenario-status":
            runner.status()
            if scenario:
                run = runner.cycle()["runs"].get(scenario)
                q.require(run is not None, "Scenario NOT PREPARED")
                runner.instructions(run)
        elif action == "scenario-prepare":
            runner.prepare(scenario, new_cycle)
        else:
            try:
                q.require(
                    runner.verify(scenario) != "FAIL", "Scenario FAIL; inspect journal; no business repair performed"
                )
            except Exception as error:
                if runner.state["cycles"]:
                    run = runner.state["cycles"][-1]["runs"].get(scenario)
                    if run:
                        run.setdefault("errors", []).append(
                            dict(
                                at=now(),
                                category=type(error).__name__,
                                diagnostic=str(error)
                                if isinstance(error, RuntimeError)
                                else "Read interrupted; no business writes; retry verify",
                            )
                        )
                        runner.persist()
                raise
