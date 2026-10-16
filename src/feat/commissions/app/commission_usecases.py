from datetime import date
from decimal import Decimal
from uuid import UUID

from src.common.domain.money import sum_amounts
from src.feat.commissions.api.commission_schemas import (
    AssignRepresentativeResp,
    ClientCommissionResp,
    CommissionPeriodResp,
    CommissionRateResp,
    CommissionSummaryResp,
    EmployeeCommissionResp,
    MonthlyCommissionsResp,
    RepresentativeCommissionResp,
    RepresentativeDetailsResp,
)
from src.feat.commissions.app.commission_uow_abcs import ICommissionsUOW
from src.feat.commissions.domain.commission_excs import InactiveCommissionTargetException, SameCommissionTargetException
from src.feat.commissions.domain.commission_models import EmployeeAccrual, PointAccrual
from src.feat.sales_rep.domain.sales_rep_excs import SalesRepresentativeNotFoundException


def _period(year: int, month: int) -> CommissionPeriodResp:
    return CommissionPeriodResp(
        year=year, month=month, date_from=date(year, month, 1), date_to=date(year + (month == 12), month % 12 + 1, 1)
    )


def _rates(entries: list[PointAccrual] | list[EmployeeAccrual]) -> list[CommissionRateResp]:
    grouped: dict[Decimal, CommissionRateResp] = {}
    for entry in entries:
        rate = grouped.setdefault(
            entry.commission_percent,
            CommissionRateResp(
                commission_percent=entry.commission_percent, turnover_base=Decimal(0), commission_payable=Decimal(0)
            ),
        )
        rate.turnover_base = sum_amounts([rate.turnover_base, entry.turnover])
        rate.commission_payable = sum_amounts([rate.commission_payable, entry.commission_payable])
    return [grouped[key] for key in sorted(grouped)]


class GetCommissionsUseCase:
    def __init__(self, uow: ICommissionsUOW) -> None:
        self._uow = uow

    async def execute(
        self, *, year: int, month: int, include_deactivated: bool = False, representative_id: UUID | None = None
    ) -> MonthlyCommissionsResp | RepresentativeDetailsResp:
        period = _period(year, month)
        async with self._uow as uow:
            repo = uow.commissions
            await repo.begin_report()
            points = await repo.point_accruals(period.date_from, period.date_to)
            representatives = await repo.representatives()
            clients = await repo.clients()
            by_representative: dict[UUID, list[PointAccrual]] = {}
            assigned: dict[UUID, set[UUID]] = {}
            for entry in points:
                if entry.sales_representative_id:
                    by_representative.setdefault(entry.sales_representative_id, []).append(entry)
            for customer in clients:
                if customer.sales_representative_id:
                    assigned.setdefault(customer.sales_representative_id, set()).add(customer.client_id)
            rep_rows = []
            for rep in representatives:
                rep_id = rep.sales_representative_id
                entries = by_representative.get(rep_id, [])
                current = assigned.get(rep_id, set())
                if not (rep.is_active or include_deactivated or current or entries or representative_id == rep_id):
                    continue
                rep_rows.append(
                    RepresentativeCommissionResp(
                        sales_representative_id=rep_id,
                        sales_representative_name=rep.name,
                        is_active=rep.is_active,
                        assigned_clients_count=len(current),
                        clients_count=len(current | {entry.client_id for entry in entries}),
                        orders_count=sum(entry.orders_count for entry in entries),
                        turnover=sum_amounts(entry.turnover for entry in entries),
                        commission_payable=sum_amounts(entry.commission_payable for entry in entries),
                        commission_rate_breakdown=_rates(entries),
                    )
                )
            if representative_id is not None:
                row = next((row for row in rep_rows if row.sales_representative_id == representative_id), None)
                if row is None:
                    raise SalesRepresentativeNotFoundException(sales_representative_id=representative_id)
                entries = by_representative.get(representative_id, [])
                historical: dict[UUID, list[PointAccrual]] = {}
                for entry in entries:
                    historical.setdefault(entry.client_id, []).append(entry)
                current = assigned.get(representative_id, set())
                details = []
                for customer in clients:
                    if customer.client_id not in current and customer.client_id not in historical:
                        continue
                    accruals = historical.get(customer.client_id, [])
                    details.append(
                        ClientCommissionResp(
                            client_id=customer.client_id,
                            client_name=customer.name,
                            phone=customer.phone,
                            is_active=customer.is_active,
                            is_currently_assigned=customer.client_id in current,
                            orders_count=sum(entry.orders_count for entry in accruals),
                            turnover=sum_amounts(entry.turnover for entry in accruals),
                            commission_payable=sum_amounts(entry.commission_payable for entry in accruals),
                            last_order_date=max((entry.last_order_date for entry in accruals), default=None),
                            commission_rate_breakdown=_rates(accruals),
                        )
                    )
                return RepresentativeDetailsResp(**row.model_dump(), period=period, clients=details)
            employees = []
            employee_entries = await repo.employee_accruals(period.date_from, period.date_to)
            by_employee: dict[UUID, list[EmployeeAccrual]] = {}
            for entry in employee_entries:
                by_employee.setdefault(entry.employee_id, []).append(entry)
            for employee in await repo.employees():
                accruals = by_employee.get(employee.employee_id, [])
                if accruals or (
                    employee.commission_percent is not None and (employee.is_active or include_deactivated)
                ):
                    employees.append(
                        EmployeeCommissionResp(
                            employee_id=employee.employee_id,
                            username=employee.username,
                            role=employee.role,
                            is_active=employee.is_active,
                            turnover_base=sum_amounts(entry.turnover for entry in accruals),
                            commission_payable=sum_amounts(entry.commission_payable for entry in accruals),
                            commission_rate_breakdown=_rates(accruals),
                        )
                    )
            total = sum_amounts(entry.turnover for entry in points)
            unassigned = sum_amounts(entry.turnover for entry in points if entry.sales_representative_id is None)
            rep_commission = sum_amounts(row.commission_payable for row in rep_rows)
            employee_commission = sum_amounts(row.commission_payable for row in employees)
            return MonthlyCommissionsResp(
                period=period,
                sales_representatives=rep_rows,
                employees=employees,
                summary=CommissionSummaryResp(
                    total_turnover=total,
                    represented_turnover=sum_amounts([total, unassigned.copy_negate()]),
                    unassigned_turnover=unassigned,
                    sales_representative_commission=rep_commission,
                    employee_commission=employee_commission,
                    total_commission_payable=sum_amounts([rep_commission, employee_commission]),
                ),
            )


class AssignRepresentativeClientsUseCase:
    def __init__(self, uow: ICommissionsUOW) -> None:
        self._uow = uow

    async def execute(self, *, actor_id: UUID, source_id: UUID, target_id: UUID | None) -> AssignRepresentativeResp:
        if source_id == target_id:
            raise SameCommissionTargetException
        async with self._uow as uow:
            ids = [source_id] + ([target_id] if target_id else [])
            representatives = {
                rep.sales_representative_id: rep for rep in await uow.commissions.lock_representatives(ids)
            }
            for rep_id in ids:
                if rep_id not in representatives:
                    raise SalesRepresentativeNotFoundException(sales_representative_id=rep_id)
            if target_id and not representatives[target_id].is_active:
                raise InactiveCommissionTargetException
            clients = await uow.commissions.assigned_clients(source_id)
            events = []
            for customer in clients:
                customer.update(actor_id=actor_id, sales_representative_id=target_id)
                events.extend(customer.pull_events())
            await uow.commit(events=events)
            return AssignRepresentativeResp(
                updated_clients_count=len(clients), target_sales_representative_id=target_id
            )
