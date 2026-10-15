from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True)
class PointAccrual:
    sales_representative_id: UUID | None
    client_id: UUID
    commission_percent: Decimal
    turnover: Decimal
    commission_payable: Decimal
    orders_count: int
    last_order_date: date


@dataclass(frozen=True)
class EmployeeAccrual:
    employee_id: UUID
    commission_percent: Decimal
    turnover: Decimal
    commission_payable: Decimal
