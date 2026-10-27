from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import ConfigDict

from src.common.api.schemas import BaseSchema


class CommissionRateResp(BaseSchema):
    commission_percent: Decimal
    turnover_base: Decimal
    commission_payable: Decimal


class RepresentativeCommissionResp(BaseSchema):
    sales_representative_id: UUID
    sales_representative_name: str
    is_active: bool
    assigned_clients_count: int
    clients_count: int
    orders_count: int
    turnover: Decimal
    commission_payable: Decimal
    commission_rate_breakdown: list[CommissionRateResp]


class EmployeeCommissionResp(BaseSchema):
    employee_id: UUID
    username: str
    role: str
    is_active: bool
    turnover_base: Decimal
    commission_payable: Decimal
    commission_rate_breakdown: list[CommissionRateResp]


class ClientCommissionResp(BaseSchema):
    client_id: UUID
    client_name: str
    phone: str
    is_active: bool
    is_currently_assigned: bool
    orders_count: int
    turnover: Decimal
    last_order_date: date | None
    commission_payable: Decimal
    commission_rate_breakdown: list[CommissionRateResp]


class CommissionPeriodResp(BaseSchema):
    year: int
    month: int
    date_from: date
    date_to: date


class CommissionSummaryResp(BaseSchema):
    total_turnover: Decimal
    employee_turnover: Decimal
    represented_turnover: Decimal
    unassigned_turnover: Decimal
    sales_representative_commission: Decimal
    employee_commission: Decimal
    total_commission_payable: Decimal


class MonthlyCommissionsResp(BaseSchema):
    period: CommissionPeriodResp
    summary: CommissionSummaryResp
    sales_representatives: list[RepresentativeCommissionResp]
    employees: list[EmployeeCommissionResp]


class RepresentativeDetailsResp(RepresentativeCommissionResp):
    period: CommissionPeriodResp
    clients: list[ClientCommissionResp]


class AssignRepresentativeReq(BaseSchema):
    model_config = ConfigDict(extra="forbid")
    target_sales_representative_id: UUID | None


class AssignRepresentativeResp(BaseSchema):
    updated_clients_count: int
    target_sales_representative_id: UUID | None
