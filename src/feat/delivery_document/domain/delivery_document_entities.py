from __future__ import annotations

from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any, Self
from uuid import UUID

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.common.domain.entities import BaseEntity
from src.core.uuid7 import uuid7
from src.feat.cars.domain.car_entities import Car
from src.feat.clients.domain.client_entities import Client
from src.feat.delivery_document.domain.delivery_document_events import (
    CancelDeliveryDocumentEvent, CreateDeliveryDocumentEvent, CreateItemEvent,
    CreatePointEvent, DeleteItemEvent, DeletePointEvent, RestoreDeliveryDocumentEvent,
    UpdateDeliveryDocumentEvent, UpdateItemEvent, UpdatePointEvent,
)
from src.feat.delivery_document.domain.delivery_document_excs import DeliveryDocumentUpdateException
from src.feat.drivers.domain.driver_entities import Driver
from src.feat.employees.domain.employee_entities import Employee
from src.feat.products.domain.product_entities import Product


class DocumentType(str, Enum):
    DELIVERY = "delivery_route_sheet"
    PICKUP = "pickup_sheet"


class Item(BaseEntity):
    __tablename__ = "delivery_document_items"

    point_id: Mapped[UUID] = mapped_column(ForeignKey("points.point_id", ondelete="CASCADE"), primary_key=True)
    product_id: Mapped[UUID] = mapped_column(ForeignKey("products.product_id"), primary_key=True)
    quantity: Mapped[int] = mapped_column(Integer)
    price: Mapped[float] = mapped_column(Float)
    product: Mapped[Product] = relationship(lazy="joined")

    _ALLOWED_UPDATE_FIELDS = {"quantity", "price"}

    @property
    def product_name(self) -> str:
        return self.product.name

    @classmethod
    def create(cls, *, actor_id: UUID, point_id: UUID, product_id: UUID, quantity: int, price: float) -> Self:
        item = cls(point_id=point_id, product_id=product_id, quantity=quantity, price=price)
        item._add_event(CreateItemEvent(actor_id=actor_id, point_id=point_id, product_id=product_id))
        return item

    def update(self, *, actor_id: UUID, quantity: int, price: float) -> None:
        changes = self._apply_update_changes(
            payload={"quantity": quantity, "price": price},
            allowed_fields=self._ALLOWED_UPDATE_FIELDS,
        )
        if changes:
            self._add_event(UpdateItemEvent(
                actor_id=actor_id, point_id=self.point_id, product_id=self.product_id, changes=changes,
            ))

    def mark_deleted(self, *, actor_id: UUID) -> None:
        self._add_event(DeleteItemEvent(actor_id=actor_id, point_id=self.point_id, product_id=self.product_id))


class Point(BaseEntity):
    __tablename__ = "points"
    UQ_DOCUMENT_CLIENT = "points_delivery_document_id_client_id_key"
    UQ_DOCUMENT_POSITION = "points_delivery_document_id_position_key"
    __table_args__ = (
        UniqueConstraint("delivery_document_id", "client_id", name=UQ_DOCUMENT_CLIENT),
        UniqueConstraint("delivery_document_id", "position", name=UQ_DOCUMENT_POSITION),
    )

    point_id: Mapped[UUID] = mapped_column(primary_key=True)
    delivery_document_id: Mapped[UUID] = mapped_column(
        ForeignKey("delivery_documents.delivery_document_id", ondelete="CASCADE"),
    )
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.client_id"))
    position: Mapped[int] = mapped_column(Integer)

    client: Mapped[Client] = relationship(lazy="joined")
    items: Mapped[list[Item]] = relationship(cascade="all, delete-orphan", lazy="selectin")
    _ALLOWED_UPDATE_FIELDS = {"client_id", "position"}

    @property
    def client_name(self) -> str:
        return self.client.name

    @property
    def phone(self) -> str:
        return self.client.phone

    @property
    def address(self) -> str:
        return self.client.address

    @property
    def default_payment_method_id(self) -> UUID | None:
        return self.client.default_payment_method_id

    @property
    def default_payment_method_name(self) -> str | None:
        return self.client.default_payment_method_name

    @property
    def sales_representative_id(self) -> UUID | None:
        return self.client.sales_representative_id

    @property
    def sales_representative_name(self) -> str | None:
        return self.client.sales_representative_name

    @classmethod
    def create(cls, *, actor_id: UUID, delivery_document_id: UUID, client_id: UUID,
               position: int, items: list[Any]) -> Self:
        point_id = uuid7()
        point = cls(point_id=point_id, delivery_document_id=delivery_document_id,
                    client_id=client_id, position=position, items=[])
        point.items = [Item.create(actor_id=actor_id, point_id=point_id,
                                   product_id=item.product_id, quantity=item.quantity, price=item.price)
                       for item in items]
        point._add_event(CreatePointEvent(actor_id=actor_id, point_id=point_id,
                                          delivery_document_id=delivery_document_id))
        return point

    def update(self, *, actor_id: UUID, client_id: UUID, position: int, items: list[Any]) -> None:
        changes = self._apply_update_changes(
            payload={"client_id": client_id, "position": position},
            allowed_fields=self._ALLOWED_UPDATE_FIELDS,
        )
        if changes:
            self._add_event(UpdatePointEvent(actor_id=actor_id, point_id=self.point_id, changes=changes))

        if not hasattr(self, "_detached_events"):
            self._detached_events = []
        existing = {item.product_id: item for item in self.items}
        updated: list[Item] = []
        requested_ids: set[UUID] = set()
        for requested in items:
            requested_ids.add(requested.product_id)
            item = existing.get(requested.product_id)
            if item is None:
                item = Item.create(actor_id=actor_id, point_id=self.point_id,
                                   product_id=requested.product_id, quantity=requested.quantity, price=requested.price)
            else:
                item.update(actor_id=actor_id, quantity=requested.quantity, price=requested.price)
            updated.append(item)
        for old_item in self.items:
            if old_item.product_id not in requested_ids:
                old_item.mark_deleted(actor_id=actor_id)
                self._detached_events.extend(old_item.pull_events())
        self.items = updated

    def mark_deleted(self, *, actor_id: UUID) -> None:
        if not hasattr(self, "_detached_events"):
            self._detached_events = []
        for item in self.items:
            item.mark_deleted(actor_id=actor_id)
            self._detached_events.extend(item.pull_events())
        self._add_event(DeletePointEvent(actor_id=actor_id, point_id=self.point_id,
                                         delivery_document_id=self.delivery_document_id))

    def pull_aggregate_events(self) -> list[Any]:
        events = self.pull_events()
        events.extend(getattr(self, "_detached_events", []))
        self._detached_events = []
        for item in self.items:
            events.extend(item.pull_events())
        return events

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._detached_events: list[Any] = []


class EditLock(BaseEntity):
    __tablename__ = "delivery_document_edit_locks"
    TTL = timedelta(minutes=2)
    delivery_document_id: Mapped[UUID] = mapped_column(
        ForeignKey("delivery_documents.delivery_document_id", ondelete="CASCADE"), primary_key=True,
    )
    employee_id: Mapped[UUID] = mapped_column(ForeignKey("employees.employee_id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    employee: Mapped[Employee] = relationship(lazy="joined")
    _ALLOWED_UPDATE_FIELDS = {"employee_id", "expires_at"}

    @property
    def owner_name(self) -> str:
        return self.employee.username

    @classmethod
    def create(cls, *, delivery_document_id: UUID, employee_id: UUID,
               expires_at: datetime) -> Self:
        return cls(delivery_document_id=delivery_document_id, employee_id=employee_id, expires_at=expires_at)

    def renew(self) -> None:
        self.expires_at = datetime.now() + self.TTL


class DeliveryDocument(BaseEntity):
    __tablename__ = "delivery_documents"
    TYPE_DELIVERY_ROUTE_SHEET = DocumentType.DELIVERY.value
    TYPE_PICKUP_SHEET = DocumentType.PICKUP.value

    delivery_document_id: Mapped[UUID] = mapped_column(primary_key=True)
    document_type: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    planned_date: Mapped[date] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(default=True)
    driver_id: Mapped[UUID | None] = mapped_column(ForeignKey("drivers.driver_id"), nullable=True)
    car_id: Mapped[UUID | None] = mapped_column(ForeignKey("cars.car_id"), nullable=True)
    start_mileage: Mapped[float | None] = mapped_column(Float, nullable=True)
    end_mileage: Mapped[float | None] = mapped_column(Float, nullable=True)

    driver: Mapped[Driver | None] = relationship(lazy="joined")
    car: Mapped[Car | None] = relationship(lazy="joined")
    points: Mapped[list[Point]] = relationship(
        cascade="all, delete-orphan", order_by="Point.position", lazy="selectin",
    )
    edit_lock: Mapped[EditLock | None] = relationship(cascade="all, delete-orphan", lazy="joined", uselist=False)
    _ALLOWED_UPDATE_FIELDS = {"planned_date", "driver_id", "car_id", "start_mileage", "end_mileage"}

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._detached_events: list[Any] = []

    @property
    def driver_name(self) -> str | None:
        return self.driver.name if self.driver else None

    @property
    def car_model_and_number(self) -> str | None:
        if self.car is None:
            return None
        return f"{self.car.model} {self.car.number}"

    @classmethod
    def create(cls, *, actor_id: UUID, document_type: str, planned_date: date,
               points: list[Any], driver_id: UUID | None = None, car_id: UUID | None = None,
               start_mileage: float | None = None, end_mileage: float | None = None) -> Self:
        if document_type not in {cls.TYPE_DELIVERY_ROUTE_SHEET, cls.TYPE_PICKUP_SHEET}:
            raise DeliveryDocumentUpdateException(field="document_type", message="Unsupported document type.")
        if document_type == cls.TYPE_DELIVERY_ROUTE_SHEET:
            if driver_id is None or car_id is None or start_mileage is None:
                raise DeliveryDocumentUpdateException(field="delivery_fields", message="Driver, car and start mileage are required.")
        elif any(value is not None for value in (driver_id, car_id, start_mileage, end_mileage)):
            raise DeliveryDocumentUpdateException(field="delivery_fields", message="Pickup sheets cannot contain delivery fields.")
        _validate_mileage(start_mileage, end_mileage)
        now = datetime.now()
        document_id = uuid7()
        document = cls(
            delivery_document_id=document_id, document_type=document_type, created_at=now,
            planned_date=planned_date, is_active=True, driver_id=driver_id, car_id=car_id,
            start_mileage=start_mileage, end_mileage=end_mileage,
            points=[Point.create(actor_id=actor_id, delivery_document_id=document_id,
                                 client_id=point.client_id, position=index, items=point.items)
                    for index, point in enumerate(points)],
        )
        document._add_event(CreateDeliveryDocumentEvent(actor_id=actor_id,
            delivery_document_id=document_id, document_type=document_type))
        return document

    def update(self, *, actor_id: UUID, request: Any) -> None:
        changes: dict[str, Any] = {}
        payload = request.changes()
        point_payload = payload.pop("points", None) if "points" in payload else None
        # A supplied points field is a complete replacement, including the empty-list case.
        points_supplied = "points" in request.model_fields_set
        root_changes = self._apply_update_changes(payload=payload, allowed_fields=self._ALLOWED_UPDATE_FIELDS)
        changes.update(root_changes)
        if points_supplied:
            if not hasattr(self, "_detached_events"):
                self._detached_events = []
            requested_points = request.points
            if requested_points is None:
                raise DeliveryDocumentUpdateException(field="points", message="Points cannot be null.")
            old_by_id = {point.point_id: point for point in self.points}
            new_points: list[Point] = []
            used_ids: set[UUID] = set()
            for position, requested in enumerate(requested_points):
                if requested.point_id is None:
                    point = Point.create(actor_id=actor_id, delivery_document_id=self.delivery_document_id,
                                         client_id=requested.client_id, position=position, items=requested.items)
                else:
                    if requested.point_id in used_ids:
                        raise DeliveryDocumentUpdateException(field="point_id", message="A point ID may appear only once.")
                    used_ids.add(requested.point_id)
                    point = old_by_id.get(requested.point_id)
                    if point is None:
                        raise DeliveryDocumentUpdateException(field="point_id", message="The point does not belong to this document.")
                    point.update(actor_id=actor_id, client_id=requested.client_id,
                                 position=position, items=requested.items)
                new_points.append(point)
            retained_ids = {point.point_id for point in new_points}
            for old_point in self.points:
                if old_point.point_id not in retained_ids:
                    old_point.mark_deleted(actor_id=actor_id)
                    self._detached_events.extend(old_point.pull_aggregate_events())
            self.points = new_points
        if self.document_type == self.TYPE_DELIVERY_ROUTE_SHEET:
            _validate_mileage(self.start_mileage, self.end_mileage)
        if changes:
            self._add_event(UpdateDeliveryDocumentEvent(actor_id=actor_id,
                delivery_document_id=self.delivery_document_id, changes=changes))

    def cancel(self, *, actor_id: UUID) -> None:
        if self.is_active:
            self.is_active = False
            self._add_event(CancelDeliveryDocumentEvent(actor_id=actor_id,
                delivery_document_id=self.delivery_document_id))

    def restore(self, *, actor_id: UUID) -> None:
        if not self.is_active:
            self.is_active = True
            self._add_event(RestoreDeliveryDocumentEvent(actor_id=actor_id,
                delivery_document_id=self.delivery_document_id))

    def pull_aggregate_events(self) -> list[Any]:
        events = self.pull_events()
        events.extend(getattr(self, "_detached_events", []))
        self._detached_events = []
        for point in self.points:
            events.extend(point.pull_aggregate_events())
        return events


def _validate_mileage(start: float | None, end: float | None) -> None:
    if end is not None and (start is None or end <= start):
        raise DeliveryDocumentUpdateException(field="end_mileage", message="End mileage must be greater than start mileage.")
