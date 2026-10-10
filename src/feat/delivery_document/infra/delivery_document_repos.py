from datetime import date, datetime
from uuid import UUID

from asyncpg import exceptions as pg_excs
from sqlalchemy import func, inspect as sa_inspect, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.orm.attributes import flag_modified

from src.feat.cars.domain.car_entities import Car
from src.feat.clients.domain.client_entities import Client
from src.feat.delivery_document.domain.abcs.delivery_document_repo_abcs import IDeliveryDocumentsRepository
from src.feat.delivery_document.domain.delivery_document_entities import DeliveryDocument, EditLock, Item, Point
from src.feat.delivery_document.domain.delivery_document_excs import (
    DeliveryDocumentEditLockNotFoundException, DeliveryDocumentEditLockNotOwnedException,
    DeliveryDocumentLockedException, DeliveryDocumentPointClientAlreadyExistsException,
    DeliveryDocumentPointProductAlreadyExistsException,
    DeliveryDocumentRelatedEntityNotFoundException, DeliveryDocumentUpdateException,
)
from src.feat.drivers.domain.driver_entities import Driver
from src.feat.employees.domain.employee_entities import Employee
from src.feat.products.domain.product_entities import Product


class DeliveryDocumentsRepository(IDeliveryDocumentsRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _document_options(self):
        return (
            joinedload(DeliveryDocument.driver),
            joinedload(DeliveryDocument.car),
            joinedload(DeliveryDocument.edit_lock).joinedload(EditLock.employee),
            selectinload(DeliveryDocument.points).joinedload(Point.client),
            selectinload(DeliveryDocument.points).selectinload(Point.items).joinedload(Item.product),
        )

    async def add(self, document: DeliveryDocument) -> None:
        self._session.add(document)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._translate_integrity_error(exc, document)
            raise

    async def update(self, document: DeliveryDocument) -> None:
        # Avoid collisions in the unique (document_id, position) constraint
        # when positions are reordered or points are added/removed. Do not do
        # this on unrelated document updates (e.g. cancel/restore).
        points_changed = sa_inspect(document).attrs.points.history.has_changes()
        positions_changed = any(
            sa_inspect(point).attrs.position.history.has_changes()
            for point in document.points
        )
        if document.points and (points_changed or positions_changed):
            with self._session.no_autoflush:
                await self._session.execute(
                    update(Point)
                    .where(Point.delivery_document_id == document.delivery_document_id)
                    .values(position=Point.position + 1_000_000),
                    execution_options={"synchronize_session": False},
                )
                for point in document.points:
                    if sa_inspect(point).persistent:
                        # Even unchanged positions must be written back after the
                        # temporary database shift used to avoid UNIQUE collisions.
                        flag_modified(point, "position")
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._translate_integrity_error(exc, document)
            raise

    async def get_by_id(self, delivery_document_id: UUID, *, document_type: str,
                        for_update: bool = False) -> DeliveryDocument | None:
        stmt = select(DeliveryDocument).where(
            DeliveryDocument.delivery_document_id == delivery_document_id,
            DeliveryDocument.document_type == document_type,
        ).options(*self._document_options()).execution_options(populate_existing=True)
        if for_update:
            stmt = stmt.with_for_update(of=DeliveryDocument)
        result = await self._session.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def get_all(self, *, document_type: str, include_cancelled: bool,
                      offset: int, limit: int) -> tuple[list[DeliveryDocument], int]:
        filters = [DeliveryDocument.document_type == document_type]
        if not include_cancelled:
            filters.append(DeliveryDocument.is_active.is_(True))
        count_result = await self._session.execute(
            select(func.count()).select_from(DeliveryDocument).where(*filters),
        )
        total = int(count_result.scalar_one())
        stmt = (select(DeliveryDocument).where(*filters)
                .options(*self._document_options())
                .order_by(DeliveryDocument.created_at.desc(), DeliveryDocument.delivery_document_id.desc())
                .offset(offset).limit(limit))
        result = await self._session.execute(stmt)
        return list(result.unique().scalars().all()), total

    async def get_edit_lock(self, delivery_document_id: UUID) -> EditLock | None:
        result = await self._session.execute(
            select(EditLock).where(EditLock.delivery_document_id == delivery_document_id)
            .options(joinedload(EditLock.employee)),
        )
        lock = result.unique().scalar_one_or_none()
        if lock is not None and lock.expires_at <= datetime.now():
            return None
        return lock

    async def acquire_edit_lock(self, *, delivery_document_id: UUID, employee_id: UUID) -> str:
        result = await self._session.execute(
            select(EditLock).where(EditLock.delivery_document_id == delivery_document_id)
            .options(joinedload(EditLock.employee)).with_for_update(of=EditLock),
        )
        lock = result.unique().scalar_one_or_none()
        now = datetime.now()
        if lock is not None and lock.expires_at > now and lock.employee_id != employee_id:
            raise DeliveryDocumentLockedException(
                delivery_document_id=delivery_document_id, owner_name=lock.owner_name,
            )
        if lock is None:
            lock = EditLock(delivery_document_id=delivery_document_id, employee_id=employee_id,
                            expires_at=now + EditLock.TTL)
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

    async def validate_active_assignments(self, *, document_type: str, planned_date: date,
                                          driver_id: UUID | None, car_id: UUID | None) -> None:
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

        with self._session.no_autoflush:
            found_clients = set(
                (
                    await self._session.execute(
                        select(Client.client_id).where(Client.client_id.in_(client_ids)),
                    )
                ).scalars(),
            ) if client_ids else set()

            found_products = set(
                (
                    await self._session.execute(
                        select(Product.product_id).where(Product.product_id.in_(product_ids)),
                    )
                ).scalars(),
            ) if product_ids else set()

        missing_clients = client_ids - found_clients
        if missing_clients:
            raise DeliveryDocumentRelatedEntityNotFoundException(
                field="client_id",
                entity_id=next(iter(missing_clients)),
            )

        missing_products = product_ids - found_products
        if missing_products:
            raise DeliveryDocumentRelatedEntityNotFoundException(
                field="product_id",
                entity_id=next(iter(missing_products)),
            )

    async def _translate_integrity_error(self, exc: IntegrityError, document: DeliveryDocument) -> None:
        original = str(exc.orig)
        pgcode = getattr(exc.orig, "pgcode", None) or getattr(getattr(exc.orig, "__cause__", None), "sqlstate", None)
        if pgcode == pg_excs.UniqueViolationError.sqlstate and Point.UQ_DOCUMENT_CLIENT in original:
            client_id = next((point.client_id for point in document.points), UUID(int=0))
            raise DeliveryDocumentPointClientAlreadyExistsException(client_id=client_id) from exc
        if pgcode == pg_excs.UniqueViolationError.sqlstate and "delivery_document_items_pkey" in original:
            entity_id = next((item.product_id for point in document.points for item in point.items), UUID(int=0))
            raise DeliveryDocumentPointProductAlreadyExistsException(product_id=entity_id) from exc
        if pgcode == pg_excs.ForeignKeyViolationError.sqlstate:
            if "points_client_id_fkey" in original:
                entity_id = next((point.client_id for point in document.points), UUID(int=0))
                raise DeliveryDocumentRelatedEntityNotFoundException(field="client_id", entity_id=entity_id) from exc
            if "delivery_document_items_product_id_fkey" in original:
                entity_id = next((item.product_id for point in document.points for item in point.items), UUID(int=0))
                raise DeliveryDocumentRelatedEntityNotFoundException(field="product_id", entity_id=entity_id) from exc
            if "delivery_documents_driver_id_fkey" in original and document.driver_id:
                raise DeliveryDocumentRelatedEntityNotFoundException(field="driver_id", entity_id=document.driver_id) from exc
            if "delivery_documents_car_id_fkey" in original and document.car_id:
                raise DeliveryDocumentRelatedEntityNotFoundException(field="car_id", entity_id=document.car_id) from exc
