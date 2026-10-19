from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from psycopg import errors as pg_excs
from pydantic import Field, TypeAdapter
from sqlalchemy import func, inspect as sa_inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from src.common.domain.events import BaseDomainEvent
from src.common.domain.money import decimal_value, line_amount, sum_amounts
from src.feat.cars.domain.car_entities import Car
from src.feat.clients.domain.client_entities import Client
from src.feat.commissions.domain.commission_entities import DocumentEmployeeCommission, PointCommission
from src.feat.delivery_document.domain.abcs.delivery_document_repo_abcs import IDeliveryDocumentsRepository
from src.feat.delivery_document.domain.delivery_day_models import DayDocumentRecord, DeliveryDay
from src.feat.delivery_document.domain.delivery_document_entities import DeliveryDocument, EditLock, Point
from src.feat.delivery_document.domain.delivery_document_excs import (
    DeliveryDocumentEditLockNotFoundException,
    DeliveryDocumentEditLockNotOwnedException,
    DeliveryDocumentLockedException,
    DeliveryDocumentPointClientAlreadyExistsException,
    DeliveryDocumentPointProductAlreadyExistsException,
    DeliveryDocumentRelatedEntityNotFoundException,
    DeliveryDocumentUpdateException,
)
from src.feat.delivery_document.infra.sql.registry import SQL
from src.feat.drivers.domain.driver_entities import Driver
from src.feat.employees.domain.employee_entities import Employee
from src.feat.products.domain.product_entities import Product
from src.feat.sales_rep.domain.sales_rep_entities import SalesRepresentative


_days_adapter = TypeAdapter(list[DeliveryDay])
_day_document_adapter = TypeAdapter(Annotated[DayDocumentRecord, Field(discriminator="document_type")])


class DeliveryDocumentsRepository(IDeliveryDocumentsRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def sync_car_mileage(
        self,
        document: DeliveryDocument,
        *,
        actor_id: UUID,
        previous_car_id: UUID | None = None,
        previous_end_mileage: float | None = None,
        previous_car_mileage: float | None = None,
    ) -> list[BaseDomainEvent]:
        if document.car_id is None:
            return []
        end_changed = document.car_id != previous_car_id or document.end_mileage != previous_end_mileage
        car_ids = set()
        if end_changed and document.end_mileage is not None:
            car_ids.add(document.car_id)
        if previous_car_mileage is not None and previous_car_id is not None:
            car_ids.add(previous_car_id)
        if not car_ids:
            return []
        # Reload after locking: joined document.car may contain a stale mileage.
        # Stable lock order also permits simultaneous replacements in opposite directions.
        with self._session.no_autoflush:
            cars = (
                await self._session.scalars(
                    select(Car)
                    .where(Car.car_id.in_(car_ids))
                    .order_by(Car.car_id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            ).all()
        events = []
        for car in cars:
            if car.car_id == previous_car_id and previous_car_mileage is not None:
                car.update(actor_id=actor_id, current_mileage=previous_car_mileage)
            elif car.car_id == document.car_id and document.end_mileage is not None:
                # Historical documents never rewind the odometer automatically.
                car.update(actor_id=actor_id, current_mileage=max(car.current_mileage, document.end_mileage))
            events.extend(car.pull_events())
        return events

    async def capture_commissions(self, document: DeliveryDocument, *, is_new: bool) -> None:
        """Capture new recipients once; recalculate amounts using historical rates."""
        with self._session.no_autoflush:
            new_points = [point for point in document.points if point.commission is None]
            assignments = {}
            if new_points:
                rows = await self._session.execute(
                    select(
                        Client.client_id,
                        SalesRepresentative.sales_representative_id,
                        SalesRepresentative.commission_percent,
                    )
                    .outerjoin(
                        SalesRepresentative,
                        (Client.sales_representative_id == SalesRepresentative.sales_representative_id)
                        & SalesRepresentative.is_active.is_(True),
                    )
                    .where(Client.client_id.in_([point.client_id for point in new_points]))
                )
                assignments = {row.client_id: row for row in rows}
            for point in document.points:
                if point.commission is None:
                    assignment = assignments[point.client_id]
                    point.commission = PointCommission(
                        point_id=point.point_id,
                        sales_representative_id=assignment.sales_representative_id,
                        commission_percent=decimal_value(assignment.commission_percent or 0),
                    )
                turnover = sum_amounts(line_amount(item.quantity, item.price) for item in point.items)
                point.commission.recalculate(turnover)
            if is_new:
                employees = (
                    await self._session.scalars(
                        select(Employee).where(Employee.is_active.is_(True), Employee.commission_percent.is_not(None))
                    )
                ).all()
                document.employee_commissions = [
                    DocumentEmployeeCommission(
                        delivery_document_id=document.delivery_document_id,
                        employee_id=employee.employee_id,
                        commission_percent=decimal_value(employee.commission_percent),
                    )
                    for employee in employees
                    if employee.commission_percent is not None
                ]
            turnover = sum_amounts(point.commission.turnover for point in document.points if point.commission)
            for entry in document.employee_commissions:
                entry.recalculate(turnover)

    async def get_days(self, *, offset: int, limit: int) -> tuple[list[DeliveryDay], int]:
        result = await self._session.execute(SQL.GET_DELIVERY_DAYS, {"offset": offset, "limit": limit})
        row = result.mappings().one()
        return _days_adapter.validate_python(row["delivery_days"]), row["total"]

    async def get_day_documents(self, *, planned_date: date, include_cancelled: bool) -> list[DayDocumentRecord]:
        result = await self._session.execute(
            SQL.GET_DAY_DOCUMENTS, {"planned_date": planned_date, "include_cancelled": include_cancelled}
        )
        return [_day_document_adapter.validate_python(dict(row)) for row in result.mappings().all()]

    def _document_options(self):
        return (
            joinedload(DeliveryDocument.driver),
            joinedload(DeliveryDocument.car),
            joinedload(DeliveryDocument.edit_lock).joinedload(EditLock.employee),
            selectinload(DeliveryDocument.points).joinedload(Point.client),
            selectinload(DeliveryDocument.points).selectinload(Point.items),
        )

    async def add(self, document: DeliveryDocument) -> None:
        self._session.add(document)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._translate_integrity_error(exc, document)
            raise

    async def update(self, document: DeliveryDocument) -> None:
        # Validate uniqueness against the final collection, allowing reordering
        # and replacement of a point by a new point for the same client.
        points_changed = sa_inspect(document).attrs.points.history.has_changes()
        positions_changed = any(sa_inspect(point).attrs.position.history.has_changes() for point in document.points)
        collection_changed = points_changed or positions_changed
        try:
            if collection_changed:
                with self._session.no_autoflush:
                    await self._session.execute(
                        text(
                            "SET CONSTRAINTS points_delivery_document_id_client_id_key, "
                            "points_delivery_document_id_position_key DEFERRED",
                        )
                    )
            await self._session.flush()
            if collection_changed:
                await self._session.execute(
                    text(
                        "SET CONSTRAINTS points_delivery_document_id_client_id_key, "
                        "points_delivery_document_id_position_key IMMEDIATE",
                    )
                )
        except IntegrityError as exc:
            await self._translate_integrity_error(exc, document)
            raise

    async def get_by_id(
        self, delivery_document_id: UUID, *, document_type: str, for_update: bool = False
    ) -> DeliveryDocument | None:
        stmt = (
            select(DeliveryDocument)
            .where(
                DeliveryDocument.delivery_document_id == delivery_document_id,
                DeliveryDocument.document_type == document_type,
            )
            .options(*self._document_options())
            .execution_options(populate_existing=True)
        )
        if for_update:
            stmt = stmt.with_for_update(of=DeliveryDocument)
        result = await self._session.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def get_all(
        self, *, document_type: str, include_cancelled: bool, offset: int, limit: int
    ) -> tuple[list[DeliveryDocument], int]:
        filters = [DeliveryDocument.document_type == document_type]
        if not include_cancelled:
            filters.append(DeliveryDocument.is_active.is_(True))
        count_result = await self._session.execute(
            select(func.count()).select_from(DeliveryDocument).where(*filters),
        )
        total = int(count_result.scalar_one())
        stmt = (
            select(DeliveryDocument)
            .where(*filters)
            .options(*self._document_options())
            .order_by(DeliveryDocument.created_at.desc(), DeliveryDocument.delivery_document_id.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.unique().scalars().all()), total

    async def get_edit_lock(self, delivery_document_id: UUID) -> EditLock | None:
        result = await self._session.execute(
            select(EditLock)
            .where(EditLock.delivery_document_id == delivery_document_id)
            .options(joinedload(EditLock.employee)),
        )
        lock = result.unique().scalar_one_or_none()
        if lock is not None and lock.expires_at <= datetime.now():
            return None
        return lock

    async def acquire_edit_lock(self, *, delivery_document_id: UUID, employee_id: UUID) -> str:
        result = await self._session.execute(
            select(EditLock)
            .where(EditLock.delivery_document_id == delivery_document_id)
            .options(joinedload(EditLock.employee))
            .with_for_update(of=EditLock),
        )
        lock = result.unique().scalar_one_or_none()
        now = datetime.now()
        if lock is not None and lock.expires_at > now and lock.employee_id != employee_id:
            raise DeliveryDocumentLockedException(
                delivery_document_id=delivery_document_id,
                owner_name=lock.owner_name,
            )
        if lock is None:
            lock = EditLock(
                delivery_document_id=delivery_document_id, employee_id=employee_id, expires_at=now + EditLock.TTL
            )
            self._session.add(lock)
        else:
            lock.employee_id = employee_id
            lock.expires_at = now + EditLock.TTL
        await self._session.flush()
        employee = await self._session.get(Employee, employee_id)
        if employee is None:
            raise DeliveryDocumentRelatedEntityNotFoundException(field="employee_id", entity_id=employee_id)
        return employee.username

    async def renew_edit_lock(self, *, delivery_document_id: UUID, employee_id: UUID) -> str:
        lock = await self.get_edit_lock(delivery_document_id)
        if lock is None:
            raise DeliveryDocumentEditLockNotFoundException(delivery_document_id=delivery_document_id)
        if lock.employee_id != employee_id:
            raise DeliveryDocumentEditLockNotOwnedException(delivery_document_id=delivery_document_id)
        lock.expires_at = datetime.now() + EditLock.TTL
        await self._session.flush()
        return lock.owner_name

    async def release_edit_lock(self, *, delivery_document_id: UUID, employee_id: UUID) -> None:
        result = await self._session.execute(
            select(EditLock).where(EditLock.delivery_document_id == delivery_document_id).with_for_update(of=EditLock),
        )
        lock = result.scalar_one_or_none()
        if lock is None or lock.expires_at <= datetime.now():
            raise DeliveryDocumentEditLockNotFoundException(delivery_document_id=delivery_document_id)
        if lock.employee_id != employee_id:
            raise DeliveryDocumentEditLockNotOwnedException(delivery_document_id=delivery_document_id)
        await self._session.delete(lock)
        await self._session.flush()

    async def validate_active_assignments(
        self, *, document_type: str, planned_date: date, driver_id: UUID | None, car_id: UUID | None
    ) -> None:
        # The contract allows past dates and repeated assignments on the same date.
        del planned_date
        if document_type == DeliveryDocument.TYPE_PICKUP_SHEET:
            return
        if driver_id is None:
            raise DeliveryDocumentUpdateException(field="driver_id", message="A driver is required for delivery.")
        if car_id is None:
            raise DeliveryDocumentUpdateException(field="car_id", message="A car is required for delivery.")
        with self._session.no_autoflush:
            driver = await self._session.get(Driver, driver_id)
            car = await self._session.get(Car, car_id)

        if driver is None or not getattr(driver, "is_active", True):
            raise DeliveryDocumentRelatedEntityNotFoundException(field="driver_id", entity_id=driver_id)
        if car is None or not getattr(car, "is_active", True):
            raise DeliveryDocumentRelatedEntityNotFoundException(field="car_id", entity_id=car_id)

    async def validate_references(self, document: DeliveryDocument) -> None:
        client_ids = {point.client_id for point in document.points}
        product_ids = {item.product_id for point in document.points for item in point.items}
        new_client_ids = {point.client_id for point in document.points if not sa_inspect(point).persistent}
        new_product_ids = {
            item.product_id for point in document.points for item in point.items if not sa_inspect(item).persistent
        }

        with self._session.no_autoflush:
            found_clients = (
                dict(
                    (
                        await self._session.execute(
                            select(Client.client_id, Client.is_active).where(Client.client_id.in_(client_ids)),
                        )
                    ).all(),
                )
                if client_ids
                else {}
            )

            found_products = (
                dict(
                    (
                        await self._session.execute(
                            select(Product.product_id, Product.is_active).where(Product.product_id.in_(product_ids)),
                        )
                    ).all(),
                )
                if product_ids
                else {}
            )

        missing_clients = client_ids - found_clients.keys()
        if missing_clients:
            raise DeliveryDocumentRelatedEntityNotFoundException(
                field="client_id",
                entity_id=next(iter(missing_clients)),
            )

        missing_products = product_ids - found_products.keys()
        if missing_products:
            raise DeliveryDocumentRelatedEntityNotFoundException(
                field="product_id",
                entity_id=next(iter(missing_products)),
            )

        if any(not found_clients[client_id] for client_id in new_client_ids):
            raise DeliveryDocumentUpdateException(field="client_id", message="New points require an active client.")
        if any(not found_products[product_id] for product_id in new_product_ids):
            raise DeliveryDocumentUpdateException(field="product_id", message="New items require an active product.")

    async def _translate_integrity_error(self, exc: IntegrityError, document: DeliveryDocument) -> None:
        original = str(exc.orig)
        pgcode = getattr(exc.orig, "pgcode", None) or getattr(getattr(exc.orig, "__cause__", None), "sqlstate", None)
        if pgcode == pg_excs.UniqueViolation.sqlstate and Point.UQ_DOCUMENT_CLIENT in original:
            client_id = next((point.client_id for point in document.points), UUID(int=0))
            raise DeliveryDocumentPointClientAlreadyExistsException(client_id=client_id) from exc
        if pgcode == pg_excs.UniqueViolation.sqlstate and "delivery_document_items_pkey" in original:
            entity_id = next((item.product_id for point in document.points for item in point.items), UUID(int=0))
            raise DeliveryDocumentPointProductAlreadyExistsException(product_id=entity_id) from exc
        if pgcode == pg_excs.ForeignKeyViolation.sqlstate:
            if "points_client_id_fkey" in original:
                entity_id = next((point.client_id for point in document.points), UUID(int=0))
                raise DeliveryDocumentRelatedEntityNotFoundException(field="client_id", entity_id=entity_id) from exc
            if "delivery_document_items_product_id_fkey" in original:
                entity_id = next((item.product_id for point in document.points for item in point.items), UUID(int=0))
                raise DeliveryDocumentRelatedEntityNotFoundException(field="product_id", entity_id=entity_id) from exc
            if "delivery_documents_driver_id_fkey" in original and document.driver_id:
                raise DeliveryDocumentRelatedEntityNotFoundException(
                    field="driver_id", entity_id=document.driver_id
                ) from exc
            if "delivery_documents_car_id_fkey" in original and document.car_id:
                raise DeliveryDocumentRelatedEntityNotFoundException(field="car_id", entity_id=document.car_id) from exc
