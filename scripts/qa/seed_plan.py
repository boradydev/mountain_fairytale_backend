"""Fixed stage-2 scenarios and independent, contract-based Decimal expectations."""

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal


VERSION = "stage2-v1"
TABLES = {
    "payment-methods": ("payment_methods", "payment_method_id"),
    "sales-representatives": ("sales_representatives", "sales_representative_id"),
    "employees": ("employees", "employee_id"),
    "drivers": ("drivers", "driver_id"),
    "cars": ("cars", "car_id"),
    "products": ("products", "product_id"),
    "clients": ("clients", "client_id"),
    "delivery-route-sheets": ("delivery_documents", "delivery_document_id"),
    "pickup-sheets": ("delivery_documents", "delivery_document_id"),
}


def money(value):
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def expectations(payload, rates, employee_rates):
    """No production imports; commission snapshots remain exact, without rounding."""
    points, warehouse = [], {}
    total = Decimal(0)
    for point in payload["points"]:
        amounts = [money(Decimal(str(i["price"])) * i["quantity"]) for i in point["items"]]
        amount = sum(amounts, Decimal(0))
        turnover = amount if point.get("isDelivered", True) else Decimal(0)
        total += turnover
        recipient, rate = rates.get(point.get("clientId"), (None, "0"))
        sales = []
        for item in point["items"]:
            if not item.get("isFreePrice", False):
                pid = item["productId"]
                warehouse[pid] = warehouse.get(pid, 0) + item["quantity"]
            sales.append(
                point.get("isDelivered", True)
                and (not item.get("isFreePrice", False) or Decimal(str(item["price"])) != 0)
            )
        points.append(
            dict(
                lineAmounts=list(map(str, amounts)),
                totalAmount=str(amount),
                turnover=str(turnover),
                recipient=recipient,
                rate=str(rate),
                commission=str(turnover * Decimal(str(rate)) / 100),
                salesIncluded=sales,
            )
        )
    return dict(
        points=points,
        totalAmount=str(total),
        warehouse=warehouse,
        employees={
            eid: dict(rate=str(rate), turnover=str(total), commission=str(total * Decimal(str(rate)) / 100))
            for eid, rate in employee_rates.items()
        },
    )


def catalogs():
    rows = []

    def add(key, kind, body, group="SHARED"):
        rows.append((key, kind, body, group))

    for i, name in enumerate(["Наличные", "Карта", "Перевод"]):
        add(f"payment{i}", "payment-methods", dict(name=f"QA-MANUAL-{name}"))
    for i, rate in enumerate(["5", "0", "2.5"]):
        add(
            f"rep{i}",
            "sales-representatives",
            dict(name=f"QA-MANUAL-Представитель-{i}", phone=f"QA-REP-000{i}", commissionPercent=rate),
        )
    for i, rate in enumerate(["1.25", "0", None]):
        add(f"employee{i}", "employees", dict(username=f"QA-MANUAL-Сотрудник-{i}", commissionPercent=rate))
    for i in range(2):
        add(f"driver{i}", "drivers", dict(name=f"QA-MANUAL-Водитель-{i}"))
        add(f"car{i}", "cars", dict(model=f"QA-MANUAL-Автомобиль-{i}", number=f"А90{i}АА99", currentMileage=100))
    for i in range(10):
        add(
            f"product{i}",
            "products",
            dict(name=f"QA-MANUAL-Товар-{i}", basePrice=str((i + 1) * 10) if i < 8 else "0", isFreePrice=i >= 8),
        )
    return rows


def clients(objects):
    roles = ["Реквизиты", "Не-доставлено", "История", "Без-заказов"]
    for i in range(30):
        group = "CORE" if i < 20 else "MANUAL"
        label = roles[(i - 20) % 4] if i >= 20 else ("Старое-имя" if i == 0 else "Клиент")
        yield (
            f"client{i}",
            "clients",
            dict(
                name=f"QA-{group}-{i:02}-{label}",
                phone=f"QA-TEST-{i:04}",
                address=f"QA-{group}-Синтетическая улица, {i}",
                deliveryDetails=f"QA-{group}-Подъезд-{i}",
                sleepingThresholdDays=30,
                salesRepresentativeId=objects[f"rep{i % 3}"]["id"] if i % 4 != 3 else None,
                defaultPaymentMethodId=objects[f"payment{i % 3}"]["id"],
            ),
            group,
        )


def documents(objects, anchor):
    def item(n, qty, price, note=""):
        p = objects[f"product{n}"]
        return dict(
            productId=p["id"],
            productName=p["initial"]["name"],
            quantity=qty,
            price=price,
            isFreePrice=n >= 8,
            driverNote=note,
        )

    # 19 CORE clients have history; client19 deliberately has none.
    groups = [[0, 1, 2, 3, 4], [5, 6, 7], [8, 9], [10, 11], [12, 13], [14, 15], [16, 17, 18], [0, 2]]
    offsets = [2, 2, 8, 16, 35, 45, 3, 1]
    for n, group in enumerate(groups):
        points = []
        for pos, c in enumerate(group):
            items = [item(pos % 8, pos + 1, str(10 + n)), item((pos + 1) % 8, 2, "12.50")]
            if n == 1 and pos == 0:
                items = [
                    item(0, 3, "0"),
                    item(8, 2, "0", "Без оценки"),
                    item(8, 3, "7.125", "Услуга А"),
                    item(9, 1, "2.005", "Услуга Б"),
                ]
            if n == 2 and pos == 0:
                items = [item(2, 1, "1.005"), item(3, 1, "1.005")]
            failed = n == 1 and pos == 1
            points.append(
                dict(
                    clientId=objects[f"client{c}"]["id"],
                    items=items,
                    paymentMethodId=objects[f"payment{pos % 3}"]["id"],
                    isDelivered=not failed,
                    nonDeliveryReason="QA-CORE: закрыто" if failed else "",
                    memo=f"QA-CORE-route{n}-point{pos}",
                )
            )
        yield (
            f"route{n}",
            "delivery-route-sheets",
            dict(
                plannedDate=(anchor - timedelta(days=offsets[n])).isoformat(),
                driverId=objects[f"driver{n % 2}"]["id"],
                carId=objects[f"car{n % 2}"]["id"],
                startMileage=100,
                points=points,
            ),
        )
    for n, offset in enumerate([2, 40, 5]):
        points = [
            dict(
                clientId=None,
                paymentMethodId=objects[f"payment{p}"]["id"] if p < 2 else None,
                items=[item(p, p + 1, "15.25")],
            )
            for p in range(3 if n == 0 else 2)
        ]
        yield (
            f"pickup{n}",
            "pickup-sheets",
            dict(plannedDate=(anchor - timedelta(days=offset)).isoformat(), points=points),
        )


def anchor_date():
    return date.today().isoformat()
