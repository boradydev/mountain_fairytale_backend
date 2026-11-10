"""Reuse QA HTTP create/recovery/mutation, with an incremental load-only journal."""

import json
import time
from collections import Counter
from decimal import Decimal
from hashlib import sha256

from scripts.load import manage as m, plan
from scripts.qa.seed import Seed, save
from scripts.qa.seed_plan import expectations
from src.common.infra.db.postgres.alembic.load_guard import require, verify


def parameters(profile, seed):
    return dict(version=plan.VERSION, database=m.DB, profile=profile, seed=seed)


class LoadSeed(Seed):
    def __init__(self, config, connection, client, args):
        self.v, self.c, self.http = config, connection, client
        self.path = m.DIRECTORY / "manifest.json"
        self.objects_dir = m.DIRECTORY / "objects"
        self.args = args
        require(1 <= args.batch_size <= 100 and 0 < args.rate <= 10, "Unsafe batch size/rate")
        self.last_request = 0
        self.dirty = None
        self.state = None
        self.instance = sha256(config["LOAD_MARKER"].encode()).hexdigest()
        if self.path.exists():
            self.state = json.loads(self.path.read_text(encoding="utf-8"))
            require(self.state.get("instance") == self.instance, "Database generation differs from manifest")
            require(
                all(self.state.get(k) == val for k, val in parameters(args.profile, args.seed).items()),
                "Manifest parameters conflict; use original profile/seed (no implicit reset)",
            )
            self.state["objects"] = {}
            for path in sorted(self.objects_dir.glob("*.json")):
                row = json.loads(path.read_text(encoding="utf-8"))
                self.state["objects"][row["key"]] = row["object"]
            pending = self.state.get("pending")
            if pending and pending.get("key") in self.state["objects"] and pending["path"].endswith("/create"):
                # Object write completed but manifest replacement was interrupted.
                require(self.state["objects"][pending["key"]]["initial"] == pending["body"], "Journal conflict")
                self.state["pending"] = None

    def summary(self):
        if not self.state:
            return {"status": "NOT SEEDED"}
        return parameters(self.args.profile, self.args.seed) | dict(
            complete=self.state["complete"],
            pending=bool(self.state.get("pending")),
            counts=dict(Counter(o["kind"] for o in self.state["objects"].values())),
        )

    def persist(self):
        if self.dirty:
            save(
                self.objects_dir / (self.dirty + ".json"),
                {"key": self.dirty, "object": self.state["objects"][self.dirty]},
            )
            self.dirty = None
        save(
            self.path,
            {k: v for k, v in self.state.items() if k != "objects"}
            | {"summary": self.summary(), "instance": self.instance},
        )

    def record(self, pending, response):
        self.dirty = pending["key"]
        super().record(pending, response)

    def mutate(self, step, key, body=None, suffix="", method="PATCH"):
        if step in self.state["steps"]:
            return
        obj = self.state["objects"][key]
        before = self.request("GET", f"/protected/{obj['kind']}/{obj['id']}")
        self.state["pending"] = dict(
            step=step,
            key=key,
            method=method,
            path=f"/protected/{obj['kind']}/{obj['id']}{suffix}",
            desired=body,
            before=before,
        )
        self.persist()
        obj["saved"] = self.request(method, self.state["pending"]["path"], body)
        self.dirty = key
        self.state["steps"].append(step)
        self.state["pending"] = None
        self.persist()

    def recover_pending(self):
        pending = self.state.get("pending")
        if (
            pending
            and pending["path"].endswith("/create")
            and pending.get("kind") in ("pickup-sheets", "delivery-route-sheets")
        ):
            corrected = plan.normalize_document(
                pending["body"], pending["kind"], self.state["objects"], self.args.profile
            )
            if corrected != pending["body"]:
                self.repair_document_intent(pending, corrected)
        if not pending or pending["path"].endswith("/create"):
            return super().recover_pending()
        obj = self.state["objects"][pending["key"]]
        current = self.request("GET", f"/protected/{obj['kind']}/{obj['id']}")
        desired = pending["desired"] or {"isActive": False}
        if all(current.get(k) == v for k, v in desired.items()):
            obj["saved"] = current
            if pending["step"] not in self.state["steps"]:
                self.state["steps"].append(pending["step"])
            self.dirty = pending["key"]
        else:
            require(current == pending["before"], "Interrupted mutation conflicts; inspect journal")
        self.state["pending"] = None
        self.persist()

    def repair_document_intent(self, pending, corrected):
        generated = next(
            (
                body
                for key, _, body in plan.documents(self.state["objects"], self.args.profile, self.args.seed)
                if key == pending["key"]
            ),
            None,
        )
        require(
            generated is not None
            and corrected == generated | {"creationRequestId": pending["body"]["creationRequestId"]},
            "Interrupted document differs from known generator input; inspect journal",
        )
        # Never alter an uncertain request that may already have committed.
        verify(self.c, self.v)
        require(
            self.c.execute(
                "SELECT delivery_document_id FROM delivery_documents WHERE creation_request_id=%s",
                (pending["body"]["creationRequestId"],),
            ).fetchone()
            is None,
            "Document already exists; refusing to change its recorded request",
        )
        objects = self.state["objects"]
        by_id = {obj["id"]: obj["initial"] for obj in objects.values()}
        rates = {}
        for point in corrected["points"]:
            if point["clientId"]:
                cid = point["clientId"]
                rid = by_id[cid]["salesRepresentativeId"]
                rates[cid] = (rid, by_id[rid]["commissionPercent"])
        employees = {objects[f"employee{i}"]["id"]: rate for i, rate in enumerate(["1.25", "0"])}
        pending["body"] = corrected
        pending["expected"] = expectations(corrected, rates, employees)
        self.persist()

    def guard(self):
        verify(self.c, self.v)
        require(
            str(self.http.base_url).rstrip("/") == m.BASE_URL
            and not self.http.follow_redirects
            and not self.http.params,
            "Unsafe HTTP target/options",
        )
        self.run_id = m.attest(self.http)

    def request(self, method, path, body=None):
        path = path.replace("/protected/employees", "/admin/employees")
        delay = 1 / self.args.rate - (time.monotonic() - self.last_request)
        if delay > 0:
            time.sleep(delay)
        if method != "GET":
            self.guard()
        self.last_request = time.monotonic()
        response = self.http.request(method, path, json=body)
        require(response.headers.get("X-Load-Run") == self.run_id, "API changed; journal retained")
        require(response.status_code < 400, f"{method} {path}: HTTP {response.status_code}; journal retained")
        return response.json()["data"]

    def verify_objects(self):
        # During create the inherited QA implementation rechecks every previous object (quadratic).
        # Here each write is read back immediately; full independent verification is a separate command.
        pending_key = getattr(self, "current_key", None)
        if pending_key and pending_key in self.state["objects"]:
            obj = self.state["objects"][pending_key]
            actual = self.request("GET", f"/protected/{obj['kind']}/{obj['id']}")
            require(actual == obj["saved"], f"Write readback mismatch: {obj['id']}")

    def create(self, key, *args, **kwargs):
        self.current_key = key
        super().create(key, *args, **kwargs)

    def run(self):
        self.guard()
        if not self.state:
            # Existing unknown data is never silently adopted.
            for table in (
                "clients",
                "delivery_documents",
                "products",
                "payment_methods",
                "cars",
                "drivers",
                "sales_representatives",
            ):
                require(
                    self.c.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0,
                    f"Nonempty {table} without manifest; refusing seed",
                )
            self.state = parameters(self.args.profile, self.args.seed) | dict(
                objects={}, steps=[], pending=None, complete=False, dateFrom=str(plan.START), dateTo=str(plan.END)
            )
            self.persist()
        self.recover_pending()
        if self.state["complete"]:
            print("Seed already complete; no business writes. Run verify.")
            return
        for row in plan.directories():
            self.create(*row)
        for row in plan.clients(self.state["objects"], plan.PROFILES[self.args.profile][0]):
            self.create(*row)
        objects = self.state["objects"]
        rates = {
            obj["id"]: (
                obj["initial"]["salesRepresentativeId"],
                objects[f"rep{int(key[6:]) % 3}"]["initial"]["commissionPercent"],
            )
            for key, obj in objects.items()
            if obj["kind"] == "clients"
        }
        employees = {objects[f"employee{i}"]["id"]: rate for i, rate in enumerate(["1.25", "0"])}
        for index, (key, kind, body) in enumerate(plan.documents(objects, self.args.profile, self.args.seed)):
            self.create(key, kind, body, "LOAD", expectations(body, rates, employees))
            if index % 17 == 0:
                self.mutate("cancel-" + key, key, suffix="/cancel", method="POST")
            if (index + 1) % self.args.batch_size == 0:
                print(f"Documents checkpoint: {index + 1}", flush=True)
                time.sleep(0.2)
        self.mutate("historical-client", "client0", dict(name="LOAD Новое имя", address="LOAD Новый адрес"))
        self.mutate("historical-rate", "rep0", dict(commissionPercent="7.5"))
        for i in range(0, plan.PROFILES[self.args.profile][0], 10):
            self.mutate(f"inactive-{i}", f"client{i}", dict(isActive=False))
        self.state["complete"] = True
        checksum = sha256()
        turnover = Decimal(0)
        for key, obj in sorted(objects.items()):
            checksum.update(json.dumps([key, obj["initial"]], sort_keys=True, ensure_ascii=False).encode())
            if obj.get("expected") and obj["saved"]["isActive"]:
                turnover += Decimal(obj["expected"]["totalAmount"])
        self.state["controls"] = dict(
            input_sha256=checksum.hexdigest(),
            active_turnover=str(turnover),
            documents=plan.PROFILES[self.args.profile][1],
            points=plan.PROFILES[self.args.profile][1] * 3,
            items=plan.PROFILES[self.args.profile][1] * 6,
        )
        self.persist()
        print(json.dumps(self.summary(), ensure_ascii=False))
