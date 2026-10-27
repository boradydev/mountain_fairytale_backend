from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.feat.clients.domain.client_entities import Client
from src.feat.commissions.domain.commission_entities import DocumentEmployeeCommission, PointCommission
from src.feat.commissions.domain.commission_models import EmployeeAccrual, PointAccrual
from src.feat.commissions.domain.commission_repo_abcs import ICommissionsRepository
from src.feat.delivery_document.domain.delivery_document_entities import DeliveryDocument, Point
from src.feat.employees.domain.employee_entities import Employee
from src.feat.sales_rep.domain.sales_rep_entities import SalesRepresentative


class CommissionsRepository(ICommissionsRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def begin_report(self) -> None:
        await self._session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))

    async def point_accruals(self, start: date, end: date) -> list[PointAccrual]:
        entry = PointCommission
        rows = await self._session.execute(
            select(
                entry.sales_representative_id,
                Point.client_id,
                entry.commission_percent,
                func.sum(entry.turnover).label("turnover"),
                func.sum(entry.commission_payable).label("commission_payable"),
                func.count().label("orders_count"),
                func.max(DeliveryDocument.planned_date).label("last_order_date"),
            )
            .join(Point, Point.point_id == entry.point_id)
            .join(DeliveryDocument, DeliveryDocument.delivery_document_id == Point.delivery_document_id)
            .where(
                DeliveryDocument.is_active.is_(True),
                DeliveryDocument.planned_date >= start,
                DeliveryDocument.planned_date < end,
            )
            .group_by(entry.sales_representative_id, Point.client_id, entry.commission_percent)
        )
        return [PointAccrual(**dict(row)) for row in rows.mappings()]

    async def employee_accruals(self, start: date, end: date) -> list[EmployeeAccrual]:
        entry = DocumentEmployeeCommission
        rows = await self._session.execute(
            select(
                entry.employee_id,
                entry.commission_percent,
                func.sum(entry.turnover).label("turnover"),
                func.sum(entry.commission_payable).label("commission_payable"),
            )
            .join(DeliveryDocument, DeliveryDocument.delivery_document_id == entry.delivery_document_id)
            .where(
                DeliveryDocument.is_active.is_(True),
                DeliveryDocument.planned_date >= start,
                DeliveryDocument.planned_date < end,
            )
            .group_by(entry.employee_id, entry.commission_percent)
        )
        return [EmployeeAccrual(**dict(row)) for row in rows.mappings()]

    async def representatives(self) -> list[SalesRepresentative]:
        return list(
            (
                await self._session.scalars(
                    select(SalesRepresentative).order_by(
                        SalesRepresentative.name, SalesRepresentative.sales_representative_id
                    )
                )
            ).all()
        )

    async def employees(self) -> list[Employee]:
        return list(
            (await self._session.scalars(select(Employee).order_by(Employee.username, Employee.employee_id))).all()
        )

    async def employee_turnover(self, start: date, end: date) -> Decimal:
        # EXISTS includes a document once, regardless of the number of recipients.
        # Snapshot presence includes an explicitly assigned 0% rate.
        has_employee = (
            select(DocumentEmployeeCommission.delivery_document_id)
            .where(DocumentEmployeeCommission.delivery_document_id == DeliveryDocument.delivery_document_id)
            .exists()
        )
        value = await self._session.scalar(
            select(func.sum(PointCommission.turnover))
            .join(Point, Point.point_id == PointCommission.point_id)
            .join(DeliveryDocument, DeliveryDocument.delivery_document_id == Point.delivery_document_id)
            .where(
                DeliveryDocument.is_active.is_(True),
                DeliveryDocument.planned_date >= start,
                DeliveryDocument.planned_date < end,
                has_employee,
            )
        )
        return value if value is not None else Decimal(0)

    async def clients(self) -> list[Client]:
        return list(
            (await self._session.scalars(select(Client).order_by(Client.name, Client.client_id))).unique().all()
        )

    async def lock_representatives(self, ids: list[UUID]) -> list[SalesRepresentative]:
        return list(
            (
                await self._session.scalars(
                    select(SalesRepresentative)
                    .where(SalesRepresentative.sales_representative_id.in_(ids))
                    .order_by(SalesRepresentative.sales_representative_id)
                    .with_for_update()
                )
            ).all()
        )

    async def assigned_clients(self, representative_id: UUID) -> list[Client]:
        return list(
            (
                await self._session.scalars(
                    select(Client)
                    .where(Client.sales_representative_id == representative_id)
                    .order_by(Client.client_id)
                    .with_for_update(of=Client)
                )
            )
            .unique()
            .all()
        )
