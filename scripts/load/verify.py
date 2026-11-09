"""Independent input/SQL/API checks, using Decimal per-line HALF_UP expectations."""

import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256

from psycopg import sql

from scripts.load import manage as m, plan
from scripts.qa.seed import save
from scripts.qa.seed_plan import TABLES, expectations, money
from src.common.infra.db.postgres.alembic.load_guard import require, verify


def equal(identity, field, expected, actual):
    require(expected == actual, f"{identity}/{field}: expected={expected!r}, actual={actual!r}")


def pages(seed, path, field, expected_ids, params):
    """Compare every page against independently sorted membership, including total and empty tail."""
    result = []
    for offset in range(0, len(expected_ids) + 50, 50):
        response = seed.http.get(path, params=params | {"limit": 50, "offset": offset})
        require(
            response.status_code == 200 and response.headers.get("X-Load-Run") == seed.run_id,
            f"Pagination request failed: {path}/{offset}",
        )
        body = response.json()
        equal(path, "total", len(expected_ids), body["total"])
        rows = body["data"][field]
        pk = "pointId" if field == "deliveries" else "deliveryDocumentId"
        actual = [row[pk] for row in rows]
        equal(path, f"page/{offset}", expected_ids[offset : offset + 50], actual)
        result.extend(rows)
    equal(path, "unique IDs", len(expected_ids), len({r[pk] for r in result}))
    return result


def check_foreign_keys(c):
    rows = c.execute("""SELECT con.conname, ns.nspname, child.relname, parent.relname,
      array_agg(ca.attname ORDER BY keys.n),array_agg(pa.attname ORDER BY keys.n),con.convalidated
      FROM pg_constraint con JOIN pg_class child ON child.oid=con.conrelid
      JOIN pg_namespace ns ON ns.oid=child.relnamespace JOIN pg_class parent ON parent.oid=con.confrelid
      CROSS JOIN LATERAL unnest(con.conkey,con.confkey) WITH ORDINALITY keys(c,p,n)
      JOIN pg_attribute ca ON ca.attrelid=child.oid AND ca.attnum=keys.c
      JOIN pg_attribute pa ON pa.attrelid=parent.oid AND pa.attnum=keys.p
      WHERE con.contype='f' AND ns.nspname='public'
      GROUP BY con.conname,ns.nspname,child.relname,parent.relname,con.convalidated""").fetchall()
    require(bool(rows), "No foreign keys found")
    for name, schema, child, parent, cols, targets, validated in rows:
        require(validated, f"Unvalidated constraint: {name}")
        match = sql.SQL(" AND ").join(
            sql.SQL("p.{}=c.{}").format(sql.Identifier(b), sql.Identifier(a))
            for a, b in zip(cols, targets, strict=True)
        )
        nonnull = sql.SQL(" AND ").join(sql.SQL("c.{} IS NOT NULL").format(sql.Identifier(a)) for a in cols)
        query = sql.SQL("SELECT count(*) FROM {}.{} c WHERE {} AND NOT EXISTS(SELECT 1 FROM {}.{} p WHERE {})")
        equal(
            name,
            "orphans",
            0,
            c.execute(
                query.format(
                    sql.Identifier(schema),
                    sql.Identifier(child),
                    nonnull,
                    sql.Identifier(schema),
                    sql.Identifier(parent),
                    match,
                )
            ).fetchone()[0],
        )


def history_checks(seed, docs):
    params = {"date_from": str(plan.START), "date_to": str(plan.END)}
    docs = sorted(docs, key=lambda o: (o["saved"]["plannedDate"], o["saved"]["createdAt"], o["id"]), reverse=True)
    ids = [o["id"] for o in docs]
    all_rows = pages(seed, "/protected/delivery-history", "documents", ids, params | {"include_cancelled": "true"})
    active = [o for o in docs if o["saved"]["isActive"]]
    pages(seed, "/protected/delivery-history", "documents", [o["id"] for o in active], params)
    points = [
        (o, p)
        for o in active
        if o["kind"] == "delivery-route-sheets"
        for p in sorted(o["saved"]["points"], key=lambda p: (p["position"], p["pointId"]))
    ]
    require(len(ids) > 50 and len(points) > 50, "QA-029 requires >50 matching records")
    client_rows = pages(
        seed, "/protected/client-delivery-history", "deliveries", [p["pointId"] for _, p in points], params
    )
    # After traversing pages, change calendar/type/search and check all subsequent pages again.
    month = params | {"date_from": "2026-06-01", "date_to": "2026-06-30"}
    for kind, api_kind in (("delivery-route-sheets", "delivery_route_sheet"), ("pickup-sheets", "pickup_sheet")):
        expected = [o["id"] for o in active if o["kind"] == kind and o["saved"]["plannedDate"].startswith("2026-06")]
        require(len(expected) > 50, f"Insufficient June {kind} data")
        pages(seed, "/protected/delivery-history", "documents", expected, month | {"document_type": api_kind})
    client_by_id = {o["id"]: o for o in seed.state["objects"].values() if o["kind"] == "clients"}
    for term in ("LOAD Клиент 00000", "LOAD Синтетическая улица 00000", "00000000"):

        def matches(point, term=term):
            card = client_by_id[point["clientId"]]["saved"]
            fields = [card[k] for k in ("name", "address", "deliveryDetails")]
            fields += [point[k] for k in ("clientName", "clientAddress", "deliveryDetails")]
            digits = "".join(ch for ch in term if ch.isascii() and ch.isdigit())
            return (
                any(term.casefold() in s.casefold() for s in fields)
                or bool(digits)
                and any(
                    digits in "".join(ch for ch in phone if ch.isascii() and ch.isdigit())
                    for phone in (card["phone"], point["phone"])
                )
            )

        selected = [(o, p) for o, p in points if o["saved"]["plannedDate"].startswith("2026-06") and matches(p)]
        require(len(selected) > 50, "Filtered client history needs >50 matches")
        pages(
            seed,
            "/protected/client-delivery-history",
            "deliveries",
            [p["pointId"] for _, p in selected],
            month | {"search": term},
        )
        selected_docs = {o["id"] for o, _ in selected}
        pages(
            seed,
            "/protected/delivery-history",
            "documents",
            [o["id"] for o in active if o["id"] in selected_docs],
            month | {"search": term, "document_type": "delivery_route_sheet"},
        )
    return {r["deliveryDocumentId"]: r for r in all_rows}, {r["pointId"]: r for r in client_rows}


def verify_all(seed):
    seed.guard()
    require(seed.state and seed.state["complete"] and not seed.state["pending"], "Complete seed required")
    objects = seed.state["objects"]
    checksum = sha256()
    for key, obj in sorted(objects.items()):
        checksum.update(json.dumps([key, obj["initial"]], sort_keys=True, ensure_ascii=False).encode())
    equal("manifest", "input checksum", seed.state["controls"]["input_sha256"], checksum.hexdigest())
    for obj in objects.values():
        if obj.get("expected"):
            continue
        live = seed.request("GET", f"/protected/{obj['kind']}/{obj['id']}")
        for field in obj["initial"]:
            equal(obj["id"], field, obj["saved"].get(field), live.get(field))
        equal(obj["id"], "isActive", obj["saved"].get("isActive"), live.get("isActive"))
    docs = [o for o in objects.values() if o.get("expected")]
    expected_clients, expected_docs = plan.PROFILES[seed.args.profile]
    equal("manifest", "documents", expected_docs, len(docs))
    counts = Counter(o["kind"] for o in objects.values())
    equal("manifest", "clients", expected_clients, counts["clients"])
    ids = [o["id"] for o in objects.values()]
    equal("manifest", "unique object IDs", len(ids), len(set(ids)))
    for kind, (table, _) in TABLES.items():
        if kind == "pickup-sheets":
            continue
        expected = len(docs) if table == "delivery_documents" else counts[kind] + (1 if table == "employees" else 0)
        equal(
            table,
            "count",
            expected,
            seed.c.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table))).fetchone()[0],
        )
    for table, expected in (("points", expected_docs * 3), ("delivery_document_items", expected_docs * 6)):
        equal(
            table,
            "count",
            expected,
            seed.c.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table))).fetchone()[0],
        )
    check_foreign_keys(seed.c)
    history, client_history = history_checks(seed, docs)
    point_commissions = {
        str(r[0]): r[1:]
        for r in seed.c.execute(
            "SELECT point_id,sales_representative_id,commission_percent,turnover,commission_payable "
            "FROM point_commissions"
        )
    }
    employee_commissions = defaultdict(dict)
    for doc, employee, rate, turnover, payable in seed.c.execute(
        "SELECT delivery_document_id,employee_id,commission_percent,turnover,commission_payable "
        "FROM document_employee_commissions"
    ):
        employee_commissions[str(doc)][str(employee)] = (rate, turnover, payable)
    client_by_id = {o["id"]: o["initial"] for o in objects.values() if o["kind"] == "clients"}
    reps = {
        o["id"]: o["initial"]["commissionPercent"] for o in objects.values() if o["kind"] == "sales-representatives"
    }
    rates = {
        cid: (card["salesRepresentativeId"], reps[card["salesRepresentativeId"]]) for cid, card in client_by_id.items()
    }
    employees = {objects[f"employee{i}"]["id"]: rate for i, rate in enumerate(["1.25", "0"])}
    monthly = defaultdict(lambda: Decimal(0))
    point_ids, item_ids = [], []
    for obj in docs:
        identity, source = obj["id"], obj["initial"]
        live = seed.request("GET", f"/protected/{obj['kind']}/{identity}")
        equal(identity, "document snapshot", obj["saved"], live)
        exp = expectations(source, rates, employees)
        equal(identity, "history total", Decimal(exp["totalAmount"]), Decimal(history[identity]["totalAmount"]))
        equal(identity, "planned date", source["plannedDate"], live["plannedDate"])
        if live["isActive"]:
            monthly[source["plannedDate"][:7]] += Decimal(exp["totalAmount"])
        equal(identity, "point count", 3, len(live["points"]))
        for point, original, expected in zip(live["points"], source["points"], exp["points"], strict=True):
            pid = point["pointId"]
            point_ids.append(pid)
            equal(pid, "clientId", original["clientId"], point["clientId"])
            for field in ("isDelivered", "nonDeliveryReason", "memo", "paymentMethodId"):
                equal(pid, field, original[field], point[field])
            if original["clientId"]:
                card = client_by_id[original["clientId"]]
                for field, origin in (
                    ("clientName", "name"),
                    ("phone", "phone"),
                    ("clientAddress", "address"),
                    ("deliveryDetails", "deliveryDetails"),
                    ("salesRepresentativeId", "salesRepresentativeId"),
                ):
                    equal(pid, field, card[origin], point[field])
            else:
                for field in ("clientName", "phone", "clientAddress", "deliveryDetails"):
                    equal(pid, field, "", point[field])
                equal(pid, "representative", None, point["salesRepresentativeId"])
            recipient, rate, turnover, payable = point_commissions.get(pid, (None, None, None, None))
            equal(
                pid,
                "commission snapshot",
                (
                    expected["recipient"],
                    Decimal(expected["rate"]),
                    Decimal(expected["turnover"]),
                    Decimal(expected["commission"]),
                ),
                (str(recipient) if recipient else None, rate, turnover, payable),
            )
            for item, original_item in zip(point["items"], original["items"], strict=True):
                item_ids.append(item["itemId"])
                for field, value in original_item.items():
                    equal(
                        item["itemId"],
                        field,
                        Decimal(value) if field == "price" else value,
                        Decimal(item[field]) if field == "price" else item[field],
                    )
            if pid in client_history:
                equal(
                    pid,
                    "history point total",
                    Decimal(expected["totalAmount"]),
                    Decimal(client_history[pid]["totalAmount"]),
                )
                actual_lines = {i["itemId"]: Decimal(i["amount"]) for i in client_history[pid]["items"]}
                for item in point["items"]:
                    equal(
                        item["itemId"],
                        "line amount",
                        money(Decimal(str(item["price"])) * item["quantity"]),
                        actual_lines[item["itemId"]],
                    )
        equal(
            identity,
            "employees",
            {
                eid: (Decimal(e["rate"]), Decimal(e["turnover"]), Decimal(e["commission"]))
                for eid, e in exp["employees"].items()
            },
            employee_commissions[identity],
        )
    for name, values in (("points", point_ids), ("items", item_ids)):
        equal(name, "unique IDs", len(values), len(set(values)))
    for month, expected in monthly.items():
        from calendar import monthrange

        year, number = map(int, month.split("-"))
        report = seed.request(
            "GET", f"/protected/sales-report?date_from={month}-01&date_to={month}-{monthrange(year, number)[1]}"
        )
        equal(month, "active delivered sales", expected, Decimal(report["totalAmount"]))
    equal(
        "manifest",
        "active turnover",
        Decimal(seed.state["controls"]["active_turnover"]),
        sum(monthly.values(), Decimal(0)),
    )
    verify(seed.c, seed.v)
    result = {
        "timestamp": datetime.now(UTC).isoformat(),
        "result": "PASS",
        "profile": seed.args.profile,
        "documents": len(docs),
        "points": len(point_ids),
        "items": len(item_ids),
        "qa029_api": "PASS",
        "qa029_flutter": "PENDING OWNER",
        "monthlyTurnover": {k: str(v) for k, v in monthly.items()},
    }
    save(m.DIRECTORY / "verification.json", result)
    print("Integrity and API pagination PASS; Flutter scroll remains PENDING OWNER")
