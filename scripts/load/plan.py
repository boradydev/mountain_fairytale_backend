"""Deterministic synthetic HTTP inputs; no production calculation imports."""

import random
from datetime import date, timedelta

from scripts.qa.seed_plan import catalogs


VERSION = "load-v1"
PROFILES = {"main": (1000, 5000), "high": (5000, 20000)}
START = date(2026, 1, 1)
END = date(2026, 12, 31)


def directories():
    for key, kind, body, _ in catalogs():
        body = dict(body)
        for field in ("name", "username", "phone", "number"):
            if field in body:
                body[field] = body[field].replace("QA-MANUAL", "LOAD").replace("QA-REP", "LOAD-REP")
        yield key, kind, body, "LOAD"


def clients(objects, count):
    for i in range(count):
        yield (
            f"client{i}",
            "clients",
            dict(
                name=f"LOAD Клиент {i:05d}",
                phone=f"LOAD-PHONE-{i:08d}",
                address=f"LOAD Синтетическая улица {i:05d}",
                deliveryDetails=f"LOAD Подъезд {i % 7}",
                sleepingThresholdDays=30,
                salesRepresentativeId=objects[f"rep{i % 3}"]["id"],
                defaultPaymentMethodId=objects[f"payment{i % 3}"]["id"],
            ),
            "LOAD",
        )


def documents(objects, profile, seed):
    count, total = PROFILES[profile]
    rng = random.Random(seed)
    for n in range(total):
        pickup = n % 10 == 9
        points = []
        for p in range(3):
            # First 300 documents share one date and client0; last 10% clients have no orders.
            c = 0 if p == 0 and n < 300 else rng.randrange(count * 9 // 10)
            failed = not pickup and (n + p) % 13 == 0
            free = not pickup and p == 2
            items = []
            for k in range(2):
                product = objects[f"product{8 if free and k == 1 else (p * 2 + k) % 8}"]
                items.append(
                    dict(
                        productId=product["id"],
                        productName=product["initial"]["name"],
                        quantity=1 + rng.randrange(5),
                        price=rng.choice(["1.005", "12.50", "27.125", "0"]),
                        isFreePrice=free and k == 1,
                        driverNote="LOAD Услуга" if free and k == 1 else "",
                    )
                )
            points.append(
                dict(
                    clientId=None if pickup else objects[f"client{c}"]["id"],
                    items=items,
                    paymentMethodId=objects[f"payment{p}"]["id"],
                    isDelivered=not failed,
                    nonDeliveryReason="LOAD Закрыто" if failed else "",
                    memo="" if pickup else f"LOAD {n}/{p}",
                )
            )
        planned = date(2026, 6, 15) if n < 300 else START + timedelta(days=rng.randrange(365))
        body = dict(plannedDate=planned.isoformat(), points=points)
        if not pickup:
            body.update(driverId=objects[f"driver{n % 2}"]["id"], carId=objects[f"car{n % 2}"]["id"], startMileage=100)
        yield f"{VERSION}-{profile}-{seed}-doc{n}", "pickup-sheets" if pickup else "delivery-route-sheets", body
