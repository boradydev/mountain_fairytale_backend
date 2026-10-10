from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.orm.attributes import get_history

from src.feat.cars.domain.car_entities import Car
from src.feat.clients.domain.client_entities import Client
from src.feat.delivery_document.domain.abcs.delivery_document_repo_abcs import (
    IDeliveryDocumentsRepository,
)
from src.feat.delivery_document.domain.delivery_document_entities import (
    DeliveryDocument,
    EditLock,
    Item,
    Point,
)
from src.feat.delivery_document.domain.delivery_document_excs import (
    DeliveryDocumentEditLockNotFoundException,
    DeliveryDocumentEditLockNotOwnedException,
    DeliveryDocumentLockedException,
    DeliveryDocumentNotFoundException,
    DeliveryDocumentRelatedEntityNotFoundException,
)
from src.feat.drivers.domain.driver_entities import Driver
from src.feat.employees.domain.employee_entities import Employee
from src.feat.products.domain.product_entities import Product


class DeliveryDocumentsRepository(IDeliveryDocumentsRepository):
    _EDIT_LOCK_TTL = timedelta(minutes=2)

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, document: DeliveryDocument) -> None:
        await self._validate_document(document=document, is_new=True)
        self._session.add(document)
        await self._session.flush()

    async def update(self, document: DeliveryDocument) -> None:
        await self._validate_document(document=document, is_new=False)
        await self._session.flush()

    async def get_by_id(
        self,
        delivery_document_id: UUID,
        *,
        document_type: str,
    ) -> DeliveryDocument | None:
        stmt = (
            select(DeliveryDocument)
            .where(
                DeliveryDocument.delivery_document_id == delivery_document_id,
                DeliveryDocument.document_type == document_type,
            )
            .options(*self._document_options())
        )
        result = await self._session.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def get_all(
        self,
        *,
        document_type: str,
        include_cancelled: bool,
        offset: int,
        limit: int,
    ) -> tuple[list[DeliveryDocument], int]:
        filters = [DeliveryDocument.document_type == document_type]
        if not include_cancelled:
            filters.append(DeliveryDocument.is_active.is_(True))

        count_stmt = (
            select(func.count())
            .select_from(DeliveryDocument)
            .where(*filters)
        )
        total = int((await self._session.execute(count_stmt)).scalar_one())

        stmt = (
            select(DeliveryDocument)
            .where(*filters)
            .order_by(DeliveryDocument.created_at.asc())
            .offset(offset)
            .limit(limit)
            .options(*self._document_options())
        )
        result = await self._session.execute(stmt)
        return list(result.unique().scalars().all()), total

    async def get_edit_lock(
        self,
        delivery_document_id: UUID,
    ) -> EditLock | None:
        stmt = (
            select(EditLock)
            .where(
                EditLock.delivery_document_id
                == delivery_document_id,
            )
            .options(joinedload(EditLock.employee))
        )
        return (await self._session.execute(stmt)).unique().scalar_one_or_none()

    async def acquire_edit_lock(
        self,
        *,
        delivery_document_id: UUID,
        employee_id: UUID,
    ) -> str:
        document = await self._get_document_for_update(delivery_document_id)
        if document is None:
            raise DeliveryDocumentNotFoundException(
                delivery_document_id=delivery_document_id,
            )

        employee = await self._session.get(Employee, employee_id)
        if employee is None:
            raise DeliveryDocumentRelatedEntityNotFoundException(
                field="employee_id",
                entity_id=employee_id,
            )

        lock = await self._get_lock_for_update(delivery_document_id)
        now = datetime.now(UTC).replace(tzinfo=None)

        if lock is not None and lock.expires_at > now and lock.employee_id != employee_id:
            raise DeliveryDocumentLockedException(
                delivery_document_id=delivery_document_id,
                owner_name=lock.employee.username,
            )

        if lock is None:
            lock = EditLock(
                delivery_document_id=delivery_document_id,
                employee_id=employee_id,
                expires_at=now + self._EDIT_LOCK_TTL,
            )
            self._session.add(lock)
        else:
            lock.employee_id = employee_id
            lock.expires_at = now + self._EDIT_LOCK_TTL

        await self._session.flush()
        return employee.username

    async def renew_edit_lock(
        self,
        *,
        delivery_document_id: UUID,
        employee_id: UUID,
    ) -> str:
        document = await self._get_document_for_update(delivery_document_id)
        if document is None:
            raise DeliveryDocumentNotFoundException(
                delivery_document_id=delivery_document_id,
            )

        lock = await self._get_lock_for_update(delivery_document_id)
        now = datetime.now(UTC).replace(tzinfo=None)

        if lock is None or lock.expires_at <= now:
            if lock is not None:
                await self._session.delete(lock)
                await self._session.flush()
            raise DeliveryDocumentEditLockNotFoundException(
                delivery_document_id=delivery_document_id,
            )

        if lock.employee_id != employee_id:
            raise DeliveryDocumentEditLockNotOwnedException(
                delivery_document_id=delivery_document_id,
            )

        lock.expires_at = now + self._EDIT_LOCK_TTL
        await self._session.flush()
        return lock.employee.username

    async def release_edit_lock(
        self,
        *,
        delivery_document_id: UUID,
        employee_id: UUID,
    ) -> None:
        document = await self._get_document_for_update(delivery_document_id)
        if document is None:
            raise DeliveryDocumentNotFoundException(
                delivery_document_id=delivery_document_id,
            )

        lock = await self._get_lock_for_update(delivery_document_id)
        now = datetime.now(UTC).replace(tzinfo=None)

        if lock is None or lock.expires_at <= now:
            if lock is not None:
                await self._session.delete(lock)
                await self._session.flush()
            raise DeliveryDocumentEditLockNotFoundException(
                delivery_document_id=delivery_document_id,
            )

        if lock.employee_id != employee_id:
            raise DeliveryDocumentEditLockNotOwnedException(
                delivery_document_id=delivery_document_id,
            )

        await self._session.delete(lock)
        await self._session.flush()

    async def validate_active_assignments(
        self,
        *,
        document_type: str,
        planned_date: object,
        driver_id: UUID | None,
        car_id: UUID | None,
    ) -> None:
        if document_type != DeliveryDocument.TYPE_DELIVERY_ROUTE_SHEET:
            return

        if driver_id is None:
            raise DeliveryDocumentRelatedEntityNotFoundException(
                field="driver_id",
                entity_id=UUID(int=0),
            )
        driver = await self._session.get(Driver, driver_id)
        if driver is None or not driver.is_active:
            raise DeliveryDocumentRelatedEntityNotFoundException(
                field="driver_id",
                entity_id=driver_id,
            )

        if car_id is None:
            raise DeliveryDocumentRelatedEntityNotFoundException(
                field="car_id",
                entity_id=UUID(int=0),
            )
        car = await self._session.get(Car, car_id)
        if car is None or not car.is_active:
            raise DeliveryDocumentRelatedEntityNotFoundException(
                field="car_id",
                entity_id=car_id,
            )

    async def _validate_document(
        self,
        *,
        document: DeliveryDocument,
        is_new: bool,
    ) -> None:
        existing_point_ids: set[UUID] = set()
        existing_item_keys: set[tuple[UUID, UUID]] = set()

        if not is_new:
            existing_point_result = await self._session.execute(
                select(Point.point_id).where(
                    Point.delivery_document_id
                    == document.delivery_document_id,
                ),
            )
            existing_point_ids = set(existing_point_result.scalars().all())

            if existing_point_ids:
                existing_item_result = await self._session.execute(
                    select(
                        Item.point_id,
                        Item.product_id,
                    ).where(
                        Item.point_id.in_(existing_point_ids),
                    ),
                )
                existing_item_keys = set(existing_item_result.tuples().all())

        driver_history = get_history(document, "driver_id")
        car_history = get_history(document, "car_id")

        assignment_changed = (
            is_new
            or driver_history.has_changes()
            or car_history.has_changes()
        )
        if assignment_changed and document.document_type == DeliveryDocument.TYPE_DELIVERY_ROUTE_SHEET:
            await self.validate_active_assignments(
                document_type=document.document_type,
                planned_date=document.planned_date,
                driver_id=document.driver_id,
                car_id=document.car_id,
            )

        point_ids = {point.point_id for point in document.points}
        new_point_ids = point_ids - existing_point_ids
        if not is_new and not existing_point_ids:
            new_point_ids = point_ids

        client_ids = {point.client_id for point in document.points}
        if client_ids:
            clients_result = await self._session.execute(
                select(Client.client_id, Client.is_active).where(
                    Client.client_id.in_(client_ids),
                ),
            )
            clients = {
                client_id: is_active
                for client_id, is_active in clients_result.tuples().all()
            }
            for point in document.points:
                is_new_point = is_new or point.point_id in new_point_ids
                is_active = clients.get(point.client_id)
                if is_active is None or (is_new_point and not is_active):
                    raise DeliveryDocumentRelatedEntityNotFoundException(
                        field="client_id",
                        entity_id=point.client_id,
                    )

        requested_product_ids = {
            item.product_id
            for point in document.points
            for item in point.items
        }
        if requested_product_ids:
            products_result = await self._session.execute(
                select(Product.product_id, Product.is_active, Product.base_price).where(
                    Product.product_id.in_(requested_product_ids),
                ),
            )
            products = {
                product_id: (is_active, float(base_price))
                for product_id, is_active, base_price in products_result.tuples().all()
            }

            for point in document.points:
                for item in point.items:
                    product_data = products.get(item.product_id)
                    item_key = (point.point_id, item.product_id)
                    is_new_item = is_new or item_key not in existing_item_keys
                    if product_data is None or (is_new_item and not product_data[0]):
                        raise DeliveryDocumentRelatedEntityNotFoundException(
                            field="product_id",
                            entity_id=item.product_id,
                        )
                    if is_new_item:
                        item.price = product_data[1]

        for point in document.points:
            point.delivery_document_id = document.delivery_document_id

    async def _get_document_for_update(
        self,
        delivery_document_id: UUID,
    ) -> DeliveryDocument | None:
        stmt = (
            select(DeliveryDocument)
            .where(
                DeliveryDocument.delivery_document_id == delivery_document_id,
            )
            .with_for_update()
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_lock_for_update(
        self,
        delivery_document_id: UUID,
    ) -> EditLock | None:
        stmt = (
            select(EditLock)
            .where(
                EditLock.delivery_document_id
                == delivery_document_id,
            )
            .options(joinedload(EditLock.employee))
            .with_for_update()
        )
        return (await self._session.execute(stmt)).unique().scalar_one_or_none()

    @staticmethod
    def _document_options() -> tuple[object, ...]:
        return (
            joinedload(DeliveryDocument.driver),
            joinedload(DeliveryDocument.car),
            selectinload(DeliveryDocument.points)
            .joinedload(Point.client)
            .joinedload(Client.sales_representative),
            selectinload(DeliveryDocument.points)
            .joinedload(Point.client)
            .joinedload(Client.default_payment_method),
            selectinload(DeliveryDocument.points)
            .selectinload(Point.items)
            .joinedload(Item.product),
        )
