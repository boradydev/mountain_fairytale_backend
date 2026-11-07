"""Guarded HTTP-only persistent QA seed; journal never contains credentials."""

import copy
import getpass
import json
import os
import secrets
import subprocess
import tomllib
from contextlib import contextmanager
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import httpx
from psycopg import sql

from scripts.qa import manage as q
from scripts.qa.seed_plan import TABLES, VERSION, anchor_date, catalogs, clients, documents, expectations, manual_phone


DIRECTORY = q.ROOT / ".codex-tmp" / "qa-seed"
MANIFEST = DIRECTORY / "manifest.json"
BASE_URL = "http://127.0.0.1:8001"


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    with temp.open("w", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    temp.replace(path)


@contextmanager
def exclusive():
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    # OS lock releases on crash; no stale sentinel requiring deletion.
    import msvcrt

    with (DIRECTORY / "seed.lock").open("a+b") as stream:
        stream.seek(0)
        if not stream.read(1):
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            raise RuntimeError("Another seed command holds the journal lock") from None
        try:
            yield
        finally:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


class Seed:
    def __init__(self, config, connection, client, path=MANIFEST):
        self.v, self.c, self.http, self.path = config, connection, client, path
        self.state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
        if self.state:
            q.require(self.state["version"] == VERSION, "Conflicting seed version")
            q.require(self.state["database"] == q.DB, "Conflicting manifest target")

    def guard(self):
        q.verify(self.c, self.v)
        q.require(str(self.http.base_url).rstrip("/") == BASE_URL, "Wrong HTTP target")
        q.require(not self.http.follow_redirects and not self.http.params, "Unsafe HTTP configuration")
        q.require(q.STATE.exists(), "No managed QA API process; run qa.ps1 start")
        state = json.loads(q.STATE.read_text(encoding="utf-8"))
        # Independently verify PID/executable/start time, as well as the run nonce.
        command = (
            f"$p=Get-Process -Id {int(state['pid'])} -ErrorAction Stop; "
            "$p.Path; $p.StartTime.ToUniversalTime().Ticks.ToString()"
        )
        lines = subprocess.check_output(["powershell", "-NoProfile", "-Command", command], text=True).splitlines()
        q.require(
            len(lines) == 2 and Path(lines[0]).resolve() == Path(os.path.realpath(os.sys._base_executable)),
            "Managed Python process mismatch",
        )
        q.require(lines[1] == state["created"], "Managed process creation time mismatch")
        response = self.http.get("/health/ready")
        response.raise_for_status()
        q.require(response.headers.get("X-QA-Run") == state["run_id"], "Wrong QA run marker")
        self.run_id = state["run_id"]
        revision = self.c.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        q.require(
            revision == ScriptDirectory.from_config(Config(str(q.ALEMBIC))).get_current_head(), "Alembic not head"
        )
        self.revision = revision

    def request(self, method, path, body=None):
        path = path.replace("/protected/employees", "/admin/employees")
        if method != "GET":
            # Recheck actual database and the managed API before every business write.
            self.guard()
        response = self.http.request(method, path, json=body)
        q.require(response.headers.get("X-QA-Run") == self.run_id, "API run changed")
        if response.status_code >= 400:
            raise RuntimeError(f"{method} {path}: HTTP {response.status_code}; journal retained")
        return response.json()["data"]

    def login(self):
        password = os.environ.get("QA_SEED_ADMIN_PASSWORD") or self.v["ADMIN_PASSWORD"]
        response = self.http.post("/public/auth/login", json=dict(username="qa_admin", password=password))
        if response.status_code == 401 and not os.environ.get("QA_SEED_ADMIN_PASSWORD"):
            password = getpass.getpass("Current QA admin password (not saved): ")
            response = self.http.post("/public/auth/login", json=dict(username="qa_admin", password=password))
        q.require(response.status_code == 200, "QA login failed; no seed business writes")
        self.http.headers["Authorization"] = "Bearer " + response.json()["data"]["accessToken"]

    def persist(self):
        save(self.path, self.state)

    def recover_pending(self):
        if not self.state or not self.state.get("pending"):
            return
        pending = self.state["pending"]
        if not pending["path"].endswith("/create"):
            obj = self.state["objects"][pending["key"]]
            current = self.request("GET", f"/protected/{obj['kind']}/{obj['id']}")
            desired = pending["desired"] or {"isActive": False}
            if all(current.get(k) == v or str(current.get(k)) == str(v) for k, v in desired.items()):
                obj["saved"] = current
                self.state["steps"].append(pending["step"])
            else:
                q.require(
                    current == pending.get("before", obj["saved"]),
                    "Interrupted mutation conflicts with current data; inspect journal",
                )
            self.state["pending"] = None
            self.persist()
            return
        kind = pending["kind"]
        if kind in ("pickup-sheets", "delivery-route-sheets"):
            # Native creationRequestId makes an uncertain POST replay safe.
            return
        table, pk = TABLES[kind]
        field = "username" if kind == "employees" else "number" if kind == "cars" else "name"
        rows = self.c.execute(
            sql.SQL("SELECT {} FROM {} WHERE {}=%s").format(
                sql.Identifier(pk), sql.Identifier(table), sql.Identifier(field)
            ),
            (pending["body"][field],),
        ).fetchall()
        q.require(len(rows) <= 1, "Ambiguous interrupted create")
        if rows:
            response = self.request("GET", f"/protected/{kind}/{rows[0][0]}")
            for key, value in pending["body"].items():
                if key != "password":
                    same = response.get(key) == value or str(response.get(key)) == str(value)
                    if key in ("commissionPercent", "basePrice", "currentMileage") and value is not None:
                        same = Decimal(str(response.get(key))) == Decimal(str(value))
                    q.require(same, f"Interrupted create differs: {pending['key']}/{key}")
            self.record(pending, response)

    def inventory(self):
        objects = self.state["objects"] if self.state else {}
        by_table = {}
        for obj in objects.values():
            by_table.setdefault(TABLES[obj["kind"]][0], set()).add(obj["id"])
        pending = self.state.get("pending") if self.state else None
        for kind, (table, pk) in TABLES.items():
            if kind == "pickup-sheets":
                continue
            rows = self.c.execute(
                sql.SQL("SELECT {} FROM {}").format(sql.Identifier(pk), sql.Identifier(table))
            ).fetchall()
            for (identity,) in rows:
                identity = str(identity)
                if (
                    table == "employees"
                    and self.c.execute("SELECT username FROM employees WHERE employee_id=%s", (identity,)).fetchone()[0]
                    == "qa_admin"
                ):
                    continue
                if identity in by_table.get(table, set()):
                    continue
                if (
                    table == "delivery_documents"
                    and pending
                    and pending["kind"] in ("delivery-route-sheets", "pickup-sheets")
                ):
                    if self.c.execute(
                        "SELECT creation_request_id FROM delivery_documents WHERE delivery_document_id=%s", (identity,)
                    ).fetchone()[0] == uuid5(NAMESPACE_URL, VERSION + pending["key"]):
                        continue
                if table == "delivery_documents" and self.state and self.state["complete"]:
                    core = [
                        obj["id"] for obj in objects.values() if obj["kind"] == "clients" and obj["group"] == "CORE"
                    ]
                    count = self.c.execute(
                        "SELECT count(*) FROM points WHERE delivery_document_id=%s AND client_id=ANY(%s::uuid[])",
                        (identity, core),
                    ).fetchone()[0]
                    q.require(count == 0, "Unknown document depends on CORE clients")
                    continue  # Owner-created MANUAL routes / anonymous pickups are preserved.
                raise RuntimeError(f"Unknown business data: {table}/{identity}; no cleanup performed")

    def record(self, pending, response):
        kind, key = pending["kind"], pending["key"]
        pk = TABLES[kind][1]
        camel = pk.split("_")[0] + "".join(x.title() for x in pk.split("_")[1:])
        self.state["objects"][key] = dict(
            kind=kind,
            group=pending["group"],
            id=response[camel],
            initial=copy.deepcopy(pending["body"]),
            saved=response,
            expected=pending.get("expected"),
        )
        self.state["pending"] = None
        self.persist()

    def create(self, key, kind, body, group="CORE", expected=None):
        if key in self.state["objects"]:
            return
        body = copy.deepcopy(body)
        if kind in ("delivery-route-sheets", "pickup-sheets"):
            body["creationRequestId"] = str(uuid5(NAMESPACE_URL, VERSION + key))
        pending = dict(
            key=key,
            kind=kind,
            body=body,
            group=group,
            method="POST",
            path=f"/protected/{kind}/create",
            expected=expected,
        )
        if self.state.get("pending"):
            q.require(self.state["pending"] == pending, "Conflicting pending step")
        self.state["pending"] = pending
        self.persist()  # Persist intent before HTTP; employee password is generated only in memory.
        outgoing = dict(body)
        if kind == "employees":
            outgoing["password"] = secrets.token_urlsafe(24)
        response = self.request("POST", pending["path"], outgoing)
        self.record(pending, response)
        self.verify_objects()

    def mutate(self, step, key, body=None, suffix="", method="PATCH"):
        if step in self.state["steps"]:
            return
        obj = self.state["objects"][key]
        path = f"/protected/{obj['kind']}/{obj['id']}{suffix}"
        self.state["pending"] = dict(
            step=step,
            key=key,
            method=method,
            path=path,
            desired=body,
            before=self.request("GET", f"/protected/{obj['kind']}/{obj['id']}"),
        )
        self.persist()
        response = self.request(method, path, body)
        obj["saved"] = response
        self.state["steps"].append(step)
        self.state["pending"] = None
        self.persist()

    def verify_objects(self):
        for key, obj in self.state["objects"].items():
            current = self.request("GET", f"/protected/{obj['kind']}/{obj['id']}")
            if obj["group"] == "MANUAL":
                continue
            # Ignore derived client last-order fields and mutable dictionary display names.
            saved = obj["saved"]
            fields = list(saved)
            if obj["kind"] in ("delivery-route-sheets", "pickup-sheets"):
                fields = ["revision", "plannedDate", "isActive", "points", "createdAt"]
            elif obj["kind"] == "clients":
                fields = list(obj["initial"]) + ["isActive"]
            elif obj["kind"] == "cars":
                fields.remove("currentMileage")  # Legitimate MANUAL trips can advance the odometer.
            for field in fields:
                if field in saved:
                    q.require(current.get(field) == saved[field], f"CORE/dependency changed: {key}/{field}")

    def update_manual_phones(self):
        """Explicit maintenance of stage2-v1; retain original inputs and resumable phone-only intents."""
        self.guard()
        q.require(self.state and self.state["complete"], "A complete stage2-v1 manifest is required")
        q.require(not self.state.get("pending"), "Finish/inspect the existing seed intent first")
        objects = self.state["objects"]
        keys = {f"client{i}" for i in range(20, 30)}
        actual_keys = {k for k, o in objects.items() if o["group"] == "MANUAL" and o["kind"] == "clients"}
        q.require(actual_keys == keys, "Unexpected MANUAL client membership")
        self.login()
        self.inventory()
        self.verify_objects()
        ledger = self.state.get("manualPhoneUpdate", {})
        q.require(set(ledger) <= keys, "Unexpected phone journal membership")
        current = {}
        # Validate every card and every target before the first PATCH.
        used = {}
        for identity, phone in self.c.execute("SELECT client_id,phone FROM clients").fetchall():
            digits = "".join(c for c in phone if "0" <= c <= "9")
            used.setdefault(digits, set()).add(str(identity))
        for index in range(20, 30):
            key, target = f"client{index}", manual_phone(index)
            obj = objects[key]
            old = obj["initial"]["phone"]
            q.require(old in (f"QA-TEST-{index:04}", target), f"Unexpected initial phone: {key}")
            card = self.request("GET", f"/protected/clients/{obj['id']}")
            q.require(card["clientId"] == obj["id"], f"Client UUID mismatch: {key}")
            q.require(
                used.get(target[1:], {obj["id"]}) <= {obj["id"]}, f"Phone already belongs to another client: {key}"
            )
            if key in ledger:
                row = ledger[key]
                q.require(row["status"] in ("pending", "done"), f"Invalid phone journal status: {key}")
                q.require(row["clientId"] == obj["id"] and row["target"] == target, f"Phone journal conflict: {key}")
                allowed = {target} if row["status"] == "done" else {row["before"]["phone"], target}
            else:
                allowed = {old, target}
            q.require(card["phone"] in allowed, f"Manual phone conflict: {key}/{obj['id']}; no overwrite")
            current[key] = card
        patches = 0
        for index in range(20, 30):
            key, target = f"client{index}", manual_phone(index)
            obj, before = objects[key], current[f"client{index}"]
            row = ledger.get(key)
            if row and row["status"] == "done":
                continue
            if row is None:
                row = dict(clientId=obj["id"], target=target, before=before, status="pending")
                ledger[key] = row
                self.state["manualPhoneUpdate"] = ledger
                self.persist()
            live = self.request("GET", f"/protected/clients/{obj['id']}")
            desired = row["before"] | {"phone": target}
            q.require(live in (row["before"], desired), f"Concurrent/manual edit: {key}; journal retained")
            if live["phone"] != target:
                response = self.request("PATCH", f"/protected/clients/{obj['id']}", {"phone": target})
                live = self.request("GET", f"/protected/clients/{obj['id']}")
                q.require(live == response, f"Phone readback mismatch: {key}; journal retained")
                patches += 1
            q.require(live == desired, f"Non-phone fields changed: {key}; journal retained")
            obj["saved"] = live
            row.update(status="done", after=live)
            self.persist()
        self.verify_objects()
        print(f"MANUAL phones verified: 10 clients, {patches} PATCH; CORE and initial inputs preserved")

    def run(self):
        self.guard()
        self.login()
        self.recover_pending()
        self.inventory()
        self.verify_objects() if self.state else None
        if self.state and self.state["complete"]:
            self.validate()
            print("Seed unchanged; CORE verified; MANUAL preserved.")
            return
        if not self.state:
            self.state = dict(
                version=VERSION,
                database=q.DB,
                anchorDate=anchor_date(),
                backendRevision=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                alembicRevision=self.revision,
                objects={},
                steps=[],
                pending=None,
                complete=False,
                limitations=[
                    "Historical representative != commission recipient: no supported public operation; not prepared.",
                    "createdAt is real server time; rolling 30-day coverage ages with anchorDate.",
                ],
            )
            self.persist()
        for args in catalogs():
            self.create(*args)
        for args in clients(self.state["objects"]):
            self.create(*args)
        objects = self.state["objects"]
        employees = {objects[f"employee{i}"]["id"]: rate for i, rate in enumerate(["1.25", "0"])}
        for key, kind, body in documents(objects, date.fromisoformat(self.state["anchorDate"])):
            if key == "route6":
                self.mutate("rate-history", "rep0", dict(commissionPercent="7.5"))
                self.mutate("inactive-rep", "rep2", dict(isActive=False))
            rates = {}
            for o in objects.values():
                if o["kind"] != "clients":
                    continue
                rep_id = o["initial"]["salesRepresentativeId"]
                rep = next((r["saved"] for r in objects.values() if r["id"] == rep_id), None)
                rates[o["id"]] = (rep_id, rep["commissionPercent"]) if rep and rep["isActive"] else (None, "0")
            self.create(key, kind, body, expected=expectations(body, rates, employees))
        self.mutate(
            "client-history",
            "client0",
            dict(
                name="QA-CORE-00-Новое-имя",
                phone="QA-TEST-9000",
                address="QA-CORE-Новый адрес, 100",
                deliveryDetails="QA-CORE-Новый подъезд",
            ),
        )
        self.mutate("product-history", "product0", dict(name="QA-MANUAL-Товар-0-Новое-имя", basePrice="99.99"))
        self.mutate("rate-history", "rep0", dict(commissionPercent="7.5"))
        self.mutate("inactive-rep", "rep2", dict(isActive=False))
        self.mutate("inactive-client", "client18", dict(isActive=False))
        self.mutate("cancel-route", "route7", suffix="/cancel", method="POST")
        self.mutate("cancel-pickup", "pickup2", suffix="/cancel", method="POST")
        self.verify_objects()
        self.validate()
        self.state["complete"] = True
        self.state["limitations"][0] = (
            "route6: inactive historical representative retained; commission recipient absent via normal create. "
            "Different non-null historical/commission representatives unsupported."
        )
        self.persist()
        print(f"Seed complete: {len(objects)} objects; manifest: {self.path}")

    def validate(self):
        """Stage-2 initial checks only, not the future general QA verifier."""
        objects = self.state["objects"]
        q.require(len(objects) == 64, "Missing seed objects")
        q.require(len({o["id"] for o in objects.values()}) == 64, "Duplicate object UUIDs")
        anchor = date.fromisoformat(self.state["anchorDate"])
        params = dict(date_from=(anchor - timedelta(days=60)).isoformat(), date_to=anchor.isoformat(), limit=100)
        history = self.request(
            "GET", "/protected/delivery-history?" + str(httpx.QueryParams(params | dict(include_cancelled="true")))
        )["documents"]
        client_history = self.request("GET", "/protected/client-delivery-history?" + str(httpx.QueryParams(params)))[
            "deliveries"
        ]
        active_history = self.request("GET", "/protected/delivery-history?" + str(httpx.QueryParams(params)))[
            "documents"
        ]
        q.require(len({p["pointId"] for p in client_history}) == len(client_history), "Duplicate client-history points")
        all_ids = []
        checked = 0
        for key, obj in objects.items():
            if not obj.get("expected"):
                continue
            expected, document = obj["expected"], obj["saved"]
            expected["isActive"] = key not in {"route7", "pickup2"}
            q.require(document["isActive"] == expected["isActive"], f"Cancellation mismatch: {key}")
            expected["plannedDate"] = obj["initial"]["plannedDate"]
            expected["pointIds"] = [p["pointId"] for p in document["points"]]
            matches = [d for d in history if d["deliveryDocumentId"] == obj["id"]]
            q.require(len(matches) == 1, f"Document missing/duplicate in history: {key}")
            q.require(matches[0]["isActive"] == expected["isActive"], f"Document history activity mismatch: {key}")
            q.require(
                sum(d["deliveryDocumentId"] == obj["id"] for d in active_history) == int(expected["isActive"]),
                f"Default history cancellation filter mismatch: {key}",
            )
            q.require(
                Decimal(matches[0]["totalAmount"]) == Decimal(expected["totalAmount"]),
                f"Document total mismatch: {key}",
            )
            for p, source, exp in zip(document["points"], obj["initial"]["points"], expected["points"], strict=True):
                exp["clientId"] = source.get("clientId")
                exp["isDelivered"] = source.get("isDelivered", True)
                exp["nonDeliveryReason"] = source.get("nonDeliveryReason", "")
                exp["itemIds"] = [i["itemId"] for i in p["items"]]
                q.require(p["position"] == document["points"].index(p), f"Purchase order mismatch: {key}")
                q.require(
                    p["isDelivered"] == exp["isDelivered"] and p["nonDeliveryReason"] == exp["nonDeliveryReason"],
                    f"Delivery state mismatch: {key}",
                )
                all_ids.append(p["pointId"])
                all_ids.extend(i["itemId"] for i in p["items"])
                q.require(p["clientId"] == source.get("clientId"), f"Client mismatch {key}")
                if source.get("clientId"):
                    client = next(o for o in objects.values() if o["id"] == source["clientId"])["initial"]
                    for target, origin in [
                        ("clientName", "name"),
                        ("phone", "phone"),
                        ("clientAddress", "address"),
                        ("deliveryDetails", "deliveryDetails"),
                        ("salesRepresentativeId", "salesRepresentativeId"),
                    ]:
                        q.require(p[target] == client[origin], f"Client snapshot differs from input: {key}/{target}")
                else:
                    q.require(p["salesRepresentativeId"] is None and p["clientName"] == "", "Non-anonymous pickup")
                for i, original in zip(p["items"], source["items"], strict=True):
                    q.require(
                        all(
                            Decimal(str(i[k])) == Decimal(str(original[k])) if k == "price" else i[k] == original[k]
                            for k in original
                        ),
                        f"Item snapshot mismatch {key}",
                    )
                rows = self.c.execute(
                    "SELECT sales_representative_id,commission_percent,turnover,commission_payable "
                    "FROM point_commissions WHERE point_id=%s",
                    (p["pointId"],),
                ).fetchall()
                q.require(len(rows) == 1, f"Missing point commission {key}")
                recipient, rate, turnover, payable = rows[0]
                q.require(
                    (str(recipient) if recipient else None, rate, turnover, payable)
                    == (exp["recipient"], Decimal(exp["rate"]), Decimal(exp["turnover"]), Decimal(exp["commission"])),
                    f"Commission mismatch {key}",
                )
                entries = [h for h in client_history if h["pointId"] == p["pointId"]]
                visible = obj["kind"] == "delivery-route-sheets" and document["isActive"]
                q.require(len(entries) == int(visible), f"Client history membership mismatch {key}")
                if entries:
                    h = entries[0]
                    q.require([i["itemId"] for i in h["items"]] == exp["itemIds"], f"History item IDs changed {key}")
                    q.require(Decimal(h["totalAmount"]) == Decimal(exp["totalAmount"]), f"Point total mismatch {key}")
                    q.require(
                        [Decimal(i["amount"]) for i in h["items"]] == list(map(Decimal, exp["lineAmounts"])),
                        f"Line amounts mismatch {key}",
                    )
                    q.require(h["isDelivered"] == source.get("isDelivered", True), f"Delivery status mismatch {key}")
                    q.require(
                        h["clientName"] == p["clientName"] and h["phone"] == p["phone"],
                        f"Historical snapshot mismatch {key}",
                    )
            rows = self.c.execute(
                "SELECT employee_id,commission_percent,turnover,commission_payable "
                "FROM document_employee_commissions WHERE delivery_document_id=%s",
                (obj["id"],),
            ).fetchall()
            actual = {str(e): dict(rate=str(r), turnover=str(t), commission=str(a)) for e, r, t, a in rows}
            q.require(set(actual) == set(expected["employees"]), f"Employee recipients mismatch {key}")
            for eid, values in actual.items():
                q.require(
                    all(Decimal(value) == Decimal(expected["employees"][eid][k]) for k, value in values.items()),
                    f"Employee commission mismatch {key}",
                )
            checked += 1
        q.require(len(all_ids) == len(set(all_ids)), "Duplicate point/item IDs")
        # Explicit dependency lists let the future verifier distinguish editable MANUAL from frozen inputs.
        self.state["coreDependencies"] = [key for key, obj in objects.items() if obj["group"] == "SHARED"]
        self.state["clientDocuments"] = {
            obj["id"]: [
                key
                for key, doc in objects.items()
                if doc.get("expected") and any(p.get("clientId") == obj["id"] for p in doc["initial"]["points"])
            ]
            for obj in objects.values()
            if obj["kind"] == "clients"
        }
        monthly = {}
        for obj in objects.values():
            if not obj.get("expected") or not obj["expected"]["isActive"]:
                continue
            exp = obj["expected"]
            month = exp["plannedDate"][:7]
            totals = monthly.setdefault(
                month, dict(turnover=Decimal(0), representativeCommission=Decimal(0), employeeCommission=Decimal(0))
            )
            totals["turnover"] += Decimal(exp["totalAmount"])
            totals["representativeCommission"] += sum((Decimal(p["commission"]) for p in exp["points"]), Decimal(0))
            totals["employeeCommission"] += sum(
                (Decimal(p["commission"]) for p in exp["employees"].values()), Decimal(0)
            )
        self.state["expectedMonthly"] = {
            month: {k: str(v) for k, v in totals.items()} for month, totals in monthly.items()
        }
        for month, expected in self.state["expectedMonthly"].items():
            year, number = map(int, month.split("-"))
            report = self.request("GET", f"/protected/commissions?year={year}&month={number}&include_deactivated=true")
            summary = report["summary"]
            for field, target in [
                ("totalTurnover", "turnover"),
                ("salesRepresentativeCommission", "representativeCommission"),
                ("employeeCommission", "employeeCommission"),
            ]:
                # New MANUAL sales legitimately change monthly reports: per-CORE SQL checks above remain valid.
                if self.c.execute("SELECT count(*) FROM delivery_documents").fetchone()[0] == 11:
                    q.require(Decimal(summary[field]) == Decimal(expected[target]), f"Monthly mismatch {month}/{field}")
        self.state["validation"] = dict(
            documentsChecked=checked,
            pointAndItemIds=len(all_ids),
            result="PASS",
            financialMethod="Independent Decimal HALF_UP per line; exact commission product / 100",
        )
        self.persist()
        print(
            f"Initial checks PASS: {checked} documents; {len(all_ids)} unique point/item IDs; "
            "financial snapshots and history"
        )


def command(v, status_only=False, manual_phones=False):
    with (
        exclusive(),
        q.connect(v) as connection,
        httpx.Client(base_url=BASE_URL, trust_env=False, timeout=30) as client,
    ):
        policy = tomllib.loads((q.ROOT / "client_compatibility.toml").read_text(encoding="utf-8"))
        client.headers["X-Client-Version"] = policy["flutter"]["min_version"]
        seed = Seed(v, connection, client)
        if manual_phones:
            seed.update_manual_phones()
        elif status_only:
            seed.guard()
            q.require(seed.state is not None, "No prepared seed manifest")
            seed.login()
            seed.recover_pending()
            seed.inventory()
            seed.verify_objects()
            q.require(seed.state["complete"], "Partial seed; run seed to continue")
            seed.validate()
            counts = {}
            for obj in seed.state["objects"].values():
                counts[obj["kind"]] = counts.get(obj["kind"], 0) + 1
            print(VERSION, "CORE:20 clients MANUAL:10 clients", counts, "manifest:", MANIFEST)
        else:
            seed.run()
