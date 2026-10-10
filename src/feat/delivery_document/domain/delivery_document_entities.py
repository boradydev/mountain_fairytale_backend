from __future__ import annotations

from datetime import date, datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any, Self
from uuid import UUID

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.common.domain.entities import BaseEntity
from src.core.uuid7 import uuid7
from src.feat.cars.domain.car_entities import Car
from src.feat.clients.domain.client_entities import Client
from src.feat.delivery_document.domain.delivery_document_events import (
    CancelDeliveryDocumentEvent,
    CreateDeliveryDocumentEvent,
    RestoreDeliveryDocumentEvent,
    UpdateDeliveryDocumentEvent,
)
from src.feat.delivery_document.domain.delivery_document_excs import (
    DeliveryDocumentUpdateException,
)
from src.feat.drivers.domain.driver_entities import Driver
from src.feat.employees.domain.employee_entities import Employee
from src.feat.products.domain.product_entities import Product

if TYPE_CHECKING:
    from src.feat.delivery_document.api.delivery_document_schemas import (
        CreateDeliveryRouteSheetReq,
        CreateItemReq,
        CreatePickupSheetReq,
        CreatePointReq,
        UpdateDeliveryRouteSheetReq,
        UpdateItemReq,
        UpdatePickupSheetReq,
        UpdatePointReq,
    )


class DocumentType(str, Enum):
    DELIVERY = "delivery"
    PICKUP = "pickup"


class Item(BaseEntity):
    __tablename__ = "items"

    point_id: Mapped[UUID] = mapped_column(
        ForeignKey("points.point_id", ondelete="CASCADE"),
        primary_key=True,
    )
    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.product_id"),
        primary_key=True,
    )
    quantity: Mapped[int] = mapped_column(Integer)
    price: Mapped[float] = mapped_column(Float)

    product: Mapped[Product] = relationship(lazy="joined")

    _ALLOWED_UPDATE_FIELDS = {
        "quantity",
        "price",
    }

    @property
    def product_name(self) -> str:
        return self.product.name

    @classmethod
    def create(
        cls,
        *,
        request: CreateItemReq,
    ) -> Self:
        return cls(
            product_id=request.product_id,
            quantity=request.quantity,
            price=request.price,
        )

    def update(
        self,
        *,
        request: UpdateItemReq,
    ) -> None:
        self._apply_update_changes(
            payload={"quantity": request.quantity},
            allowed_fields=self._ALLOWED_UPDATE_FIELDS,
        )


class Point(BaseEntity):
    __tablename__ = "points"
    UQ_DELIVERY_DOCUMENT_ID_CLIENT_ID = "points_delivery_document_id_client_id_key"
    __table_args__ = (
        UniqueConstraint(
            "delivery_document_id",
            "client_id",
            name=UQ_DELIVERY_DOCUMENT_ID_CLIENT_ID,
        ),
    )

    point_id: Mapped[UUID] = mapped_column(primary_key=True)
    delivery_document_id: Mapped[UUID] = mapped_column(
        ForeignKey("delivery_documents.delivery_document_id", ondelete="CASCADE"),
    )
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.client_id"))
    position: Mapped[int] = mapped_column(Integer)

    client: Mapped[Client] = relationship(lazy="joined")
    items: Mapped[list[Item]] = relationship(
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    _ALLOWED_UPDATE_FIELDS = {
        "position",
    }

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
    def create(
        cls,
        *,
        request: CreatePointReq,
    ) -> Self:
        from src.feat.delivery_document.api.delivery_document_schemas import (
            CreateItemReq,
        )

        return cls(
            point_id=uuid7(),
            client_id=request.client_id,
            position=request.position,
            items=[
                Item.create(
                    request=CreateItemReq(
                        product_id=item.product_id,
                        quantity=item.quantity,
                        price=item.price,
                    ),
                )
                for item in request.items
            ],
        )

    def update(
        self,
        *,
        request: UpdatePointReq,
    ) -> None:
        from src.feat.delivery_document.api.delivery_document_schemas import (
            UpdateItemReq,
        )

        if self.client_id != request.client_id:
            raise DeliveryDocumentUpdateException(
                field="client_id",
                message="The client of an existing point cannot be changed.",
            )

        self._apply_update_changes(
            payload=request.changes,
            allowed_fields=self._ALLOWED_UPDATE_FIELDS,
        )

        existing_items = {item.product_id: item for item in self.items}
        updated_items: list[Item] = []

        for requested_item in request.items:
            item = existing_items.get(requested_item.product_id)
            if item is None:
                item = Item(
                    product_id=requested_item.product_id,
                    quantity=requested_item.quantity,
                    price=0,
                )
            else:
                item.update(
                    request=UpdateItemReq(
                        product_id=requested_item.product_id,
                        quantity=requested_item.quantity,
                    ),
                )
            updated_items.append(item)

        self.items = updated_items


class EditLock(BaseEntity):
    __tablename__ = "edit_locks"

    TTL = timedelta(minutes=2)
    _ALLOWED_UPDATE_FIELDS = {
        "employee_id",
        "expires_at",
    }

    delivery_document_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "delivery_documents.delivery_document_id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )
    employee_id: Mapped[UUID] = mapped_column(ForeignKey("employees.employee_id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime)

    employee: Mapped[Employee] = relationship(lazy="joined")

    @property
    def owner_name(self) -> str:
        return self.employee.username

    @classmethod
    def create(
        cls,
        *,
        employee_id: UUID,
        expires_at: datetime,
    ) -> Self:
        return cls(
            employee_id=employee_id,
            expires_at=expires_at,
        )

    def update(self, **payload: Any) -> None:
        self._apply_update_changes(
            payload=payload,
            allowed_fields=self._ALLOWED_UPDATE_FIELDS,
        )


class DeliveryDocument(BaseEntity):
    __tablename__ = "delivery_documents"

    delivery_document_id: Mapped[UUID] = mapped_column(primary_key=True)
    document_type: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    planned_date: Mapped[date] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(default=True)

    driver_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("drivers.driver_id"),
        nullable=True,
    )
    car_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("cars.car_id"),
        nullable=True,
    )
    start_mileage: Mapped[float | None] = mapped_column(Float, nullable=True)
    end_mileage: Mapped[float | None] = mapped_column(Float, nullable=True)

    driver: Mapped[Driver | None] = relationship(lazy="joined")
    car: Mapped[Car | None] = relationship(lazy="joined")
    points: Mapped[list[Point]] = relationship(
        cascade="all, delete-orphan",
        order_by="Point.position",
        lazy="selectin",
    )
    edit_lock: Mapped[EditLock | None] = relationship(
        cascade="all, delete-orphan",
        lazy="joined",
        uselist=False,
    )

    _ALLOWED_UPDATE_FIELDS = {
        "planned_date",
        "driver_id",
        "car_id",
        "start_mileage",
        "end_mileage",
    }

    @property
    def driver_name(self) -> str | None:
        return self.driver.name if self.driver is not None else None

    @property
    def car_model(self) -> str | None:
        return self.car.model if self.car is not None else None

    @property
    def car_number(self) -> str | None:
        return self.car.number if self.car is not None else None

    @classmethod
    def create(
        cls,
        *,
        actor_id: UUID,
        request: CreateDeliveryRouteSheetReq | CreatePickupSheetReq,
    ) -> Self:
        created_at = datetime.now()

        if isinstance(request, CreateDeliveryRouteSheetReq):
            document_type = DocumentType.DELIVERY
            driver_id = request.driver_id
            car_id = request.car_id
            start_mileage = request.start_mileage
            end_mileage = request.end_mileage
        else:
            document_type = DocumentType.PICKUP
            driver_id = None
            car_id = None
            start_mileage = None
            end_mileage = None

        document = cls(
            delivery_document_id=uuid7(),
            document_type=document_type,
            created_at=created_at,
            planned_date=request.planned_date,
            is_active=True,
            driver_id=driver_id,
            car_id=car_id,
            start_mileage=start_mileage,
            end_mileage=end_mileage,
            points=[
                Point.create(
                    request=point,
                    position=position,
                )
                for point in request.points
            ],
            edit_lock=EditLock.create(
                employee_id=actor_id,
                expires_at=created_at + EditLock.TTL,
            ),
        )

        document._add_event(
            CreateDeliveryDocumentEvent(
                actor_id=actor_id,
                delivery_document_id=document.delivery_document_id,
                document_type=document_type,
            ),
        )
        return document

    def update(
        self,
        *,
        actor_id: UUID,
        request: UpdateDeliveryRouteSheetReq | UpdatePickupSheetReq,
    ) -> None:
        from src.feat.delivery_document.api.delivery_document_schemas import (
            UpdateDeliveryRouteSheetReq,
        )

        payload: dict[str, Any] = {}

        if "planned_date" in request.model_fields_set:
            payload["planned_date"] = request.planned_date

        if isinstance(request, UpdateDeliveryRouteSheetReq):
            if "driver_id" in request.model_fields_set:
                payload["driver_id"] = request.driver_id
            if "car_id" in request.model_fields_set:
                payload["car_id"] = request.car_id
            if "start_mileage" in request.model_fields_set:
                payload["start_mileage"] = request.start_mileage
            if "end_mileage" in request.model_fields_set:
                payload["end_mileage"] = request.end_mileage

        changes = self._apply_update_changes(
            payload=payload,
            allowed_fields=self._ALLOWED_UPDATE_FIELDS,
        )

        if "points" in request.model_fields_set and request.points is not None:
            old_points = self._points_snapshot(self.points)
            existing_points = {
                point.point_id: point
                for point in self.points
            }
            updated_points: list[Point] = []

            for position, requested_point in enumerate(request.points):
                if requested_point.point_id is None:
                    from src.feat.delivery_document.api.delivery_document_schemas import (
                        CreateItemReq,
                    )

                    point = Point(
                        point_id=uuid7(),
                        client_id=requested_point.client_id,
                        position=position,
                        items=[
                            Item.create(
                                request=CreateItemReq(
                                    product_id=item.product_id,
                                    quantity=item.quantity,
                                    price=0,
                                ),
                            )
                            for item in requested_point.items
                        ],
                    )
                else:
                    point = existing_points.get(requested_point.point_id)
                    if point is None:
                        raise DeliveryDocumentUpdateException(
                            field="point_id",
                            message="The point does not belong to this document.",
                        )
                    point.update(
                        request=requested_point,
                        position=position,
                    )

                updated_points.append(point)

            self.points = updated_points
            new_points = self._points_snapshot(self.points)
            if old_points != new_points:
                changes["points"] = {
                    "old": old_points,
                    "new": new_points,
                }

        if not changes:
            return

        self._add_event(
            UpdateDeliveryDocumentEvent(
                actor_id=actor_id,
                delivery_document_id=self.delivery_document_id,
                changes=changes,
            ),
        )

    def cancel(self, *, actor_id: UUID) -> None:
        if not self.is_active:
            return

        self.is_active = False
        self._add_event(
            CancelDeliveryDocumentEvent(
                actor_id=actor_id,
                delivery_document_id=self.delivery_document_id,
            ),
        )

    def restore(self, *, actor_id: UUID) -> None:
        if self.is_active:
            return

        self.is_active = True
        self._add_event(
            RestoreDeliveryDocumentEvent(
                actor_id=actor_id,
                delivery_document_id=self.delivery_document_id,
            ),
        )

    @staticmethod
    def _points_snapshot(
        points: list[Point],
    ) -> list[dict[str, Any]]:
        return [
            {
                "point_id": str(point.point_id),
                "client_id": str(point.client_id),
                "position": point.position,
                "items": [
                    {
                        "product_id": str(item.product_id),
                        "quantity": item.quantity,
                        "price": item.price,
                    }
                    for item in point.items
                ],
            }
            for point in points
        ]
