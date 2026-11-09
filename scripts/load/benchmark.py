"""Bounded real HTTP baseline: warmup, sequential or at most four concurrent requests."""

import json
import math
import statistics
import subprocess
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from scripts.load import manage as m, plan
from scripts.qa.seed import save
from src.common.infra.db.postgres.alembic.load_guard import require


def statistics_for(samples, elapsed):
    values = sorted(s[0] for s in samples)
    errors = Counter(s[1] for s in samples if s[1])
    require(bool(values) and elapsed > 0, "Empty timing sample")
    return dict(
        requests=len(values),
        successful=len(values) - sum(errors.values()),
        errors=dict(errors),
        min_ms=values[0],
        p50_ms=statistics.median(values),
        p95_ms=values[math.ceil(len(values) * 0.95) - 1],
        max_ms=values[-1],
        requests_per_second=len(values) / elapsed,
        elapsed_seconds=elapsed,
    )


def resources():
    """Optional Windows process snapshot; no dependencies and no new server processes."""
    try:
        state = json.loads(m.STATE.read_text(encoding="utf-8"))
        pid = int(state["pid"])
        script = (
            f"$p=Get-Process -Id {pid} -ErrorAction Stop; "
            "@{cpu=$p.CPU;resident_bytes=$p.WorkingSet64;"
            "created=$p.StartTime.ToUniversalTime().Ticks.ToString()} | ConvertTo-Json -Compress"
        )
        sample = json.loads(
            subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", script], text=True, stderr=subprocess.DEVNULL, timeout=5
            )
        )
        require(sample["created"] == state["created"], "Resource sampler PID identity mismatch")
        return sample
    except Exception:
        return None


def scenarios(seed):
    dates = {"date_from": str(plan.START), "date_to": str(plan.END)}
    month = {"date_from": "2026-06-01", "date_to": "2026-06-30"}
    route = next(o for o in seed.state["objects"].values() if o["kind"] == "delivery-route-sheets")
    return {
        "clients": ("/protected/clients", {"limit": 50}),
        "clients_name": ("/protected/clients", {"search": "LOAD Клиент 00000"}),
        "clients_address": ("/protected/clients", {"search": "Синтетическая улица 00000"}),
        "clients_phone": ("/protected/clients", {"search": "00000000"}),
        "client_history": ("/protected/client-delivery-history", month | {"search": "LOAD", "limit": 50}),
        "client_history_page2": ("/protected/client-delivery-history", dates | {"limit": 50, "offset": 50}),
        "client_history_page3": ("/protected/client-delivery-history", dates | {"limit": 50, "offset": 100}),
        "document_history": ("/protected/delivery-history", month | {"document_type": "delivery_route_sheet"}),
        "pickup_history": ("/protected/delivery-history", month | {"document_type": "pickup_sheet"}),
        "route_full": (f"/protected/delivery-route-sheets/{route['id']}", {}),
        "sales_month": ("/protected/sales-report", month),
        **{
            f"directory_{name}": (f"/protected/{name}", {})
            for name in ("products", "payment-methods", "drivers", "cars", "employees", "sales-representatives")
        },
    }


def benchmark(seed, requests, concurrency):
    require(1 <= requests <= 100 and 1 <= concurrency <= 4, "Benchmark bounds: requests 1..100, concurrency 1..4")
    require(seed.state and seed.state["complete"] and not seed.state["pending"], "Complete seed required")
    seed.guard()
    save(m.DIRECTORY / "benchmark.json", {"status": "RUNNING", "timestamp": datetime.now(UTC).isoformat()})
    results = {}

    def measure(path, params):
        start = time.perf_counter()
        error = None
        try:
            response = seed.http.get(path, params=params)
            if response.headers.get("X-Load-Run") != seed.run_id:
                error = "attestation"
            elif response.status_code != 200:
                error = f"HTTP_{response.status_code}"
            elif "data" not in response.json():
                error = "response_schema"
        except Exception as exc:
            error = type(exc).__name__
        return (time.perf_counter() - start) * 1000, error

    for name, (path, params) in scenarios(seed).items():
        for _ in range(2):
            _, error = measure(path, params)
            require(error is None, f"Warmup failed: {name}/{error}")
        before = resources()
        start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            samples = list(pool.map(lambda _, path=path, params=params: measure(path, params), range(requests)))
        elapsed = time.perf_counter() - start
        after = resources()
        results[name] = statistics_for(samples, elapsed)
        if before and after:
            results[name]["api_resources"] = dict(
                resident_bytes=after["resident_bytes"],
                cpu_seconds=after["cpu"] - before["cpu"],
                cpu_percent_one_core=(after["cpu"] - before["cpu"]) / elapsed * 100,
            )
        print(f"{name}: p50={results[name]['p50_ms']:.1f} ms, p95={results[name]['p95_ms']:.1f} ms", flush=True)
        time.sleep(0.2)
    result = dict(
        timestamp=datetime.now(UTC).isoformat(),
        profile=seed.args.profile,
        seed=seed.args.seed,
        concurrency=concurrency,
        warmup_per_scenario=2,
        results=results,
        resource_sampling="Optional managed API Get-Process snapshots; not PostgreSQL or peak memory",
        limitations="Includes connection guards; nearest-rank p95; small samples are exploratory, no SLA",
    )
    save(m.DIRECTORY / "benchmark.json", result)
    save(m.DIRECTORY / f"benchmark-{time.time_ns()}-c{concurrency}.json", result)
    require(
        all(r["successful"] == r["requests"] for r in results.values()), "Benchmark contains errors; inspect report"
    )
