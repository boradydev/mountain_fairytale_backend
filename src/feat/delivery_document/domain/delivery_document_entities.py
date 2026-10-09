from datetime import date, datetime
from typing import Any, Self
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.common.domain.entities import BaseEntity
from src.core.uuid7 import uuid7
from src.feat.cars.domain.car_entities import Car
from src.feat.clients.domain.client_entities import Client
from src.feat.drivers.domain.driver_entities import Driver
from src.feat.employees.domain.employee_entities import Employee
from src.feat.products.domain.product_entities import Product
from src.feat.delivery_document.domain.delivery_document_events import (
    CancelDeliveryDocumentEvent,
    CreateDeliveryDocumentEvent,
    RestoreDeliveryDocumentEvent,
    UpdateDeliveryDocumentEvent,
)


class DeliveryDocument(BaseEntity):
    __tablename__ = "delivery_documents"

    CK_DOCUMENT_TYPE = "delivery_documents_document_type_check"
    CK_DELIVERY_FIELDS = "delivery_documents_delivery_fields_check"
    CK_MILEAGE = "delivery_documents_mileage_check"

    __table_args__ = (
        CheckConstraint(
            "document_type IN ('delivery_route_sheet', 'pickup_sheet')",
            name=CK_DOCUMENT_TYPE,
        ),
        CheckConstraint(
            """
            (
                document_type = 'delivery_route_sheet'
                AND driver_id IS NOT NULL
                AND car_id IS NOT NULL
                AND start_mileage IS NOT NULL
            )
            OR
            (
                document_type = 'pickup_sheet'
                AND driver_id IS NULL
                AND car_id IS NULL
                AND start_mileage IS NULL
                AND end_mileage IS NULL
            )
            """,
            name=CK_DELIVERY_FIELDS,
        ),
        CheckConstraint(
            "end_mileage IS NULL OR end_mileage > start_mileage",
            name=CK_MILEAGE,
        ),
    )

    delivery_document_id: Mapped[UUID] = mapped_column(primary_key=True)
    document_type: Mapped[str] = mapped_column(String(32))
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
    points: Mapped[list["DeliveryDocumentPoint"]] = relationship(
        back_populates="delivery_document",
        cascade="all, delete-orphan",
        order_by="DeliveryDocumentPoint.position",
        lazy="selectin",
    )

    TYPE_DELIVERY_ROUTE_SHEET = "delivery_route_sheet"
    TYPE_PICKUP_SHEET = "pickup_sheet"

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
    def car_model_and_number(self) -> str | None:
        if self.car is None:
            return None
        return f"{self.car.model} {self.car.number}"

    @classmethod
    def create(
        cls,
        *,
        actor_id: UUID,
        document_type: str,
        planned_date: date,
        points: list["DeliveryDocumentPoint"],
        driver_id: UUID | None = None,
        car_id: UUID | None = None,
        start_mileage: float | None = None,
        end_mileage: float | None = None,
    ) -> Self:
        document = cls(
            delivery_document_id=uuid7(),
            document_type=document_type,
            created_at=datetime.now(),
            planned_date=planned_date,
            is_active=True,
            driver_id=driver_id,
            car_id=car_id,
            start_mileage=start_mileage,
            end_mileage=end_mileage,
            points=points,
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
        points: list["DeliveryDocumentPoint"] | None = None,
        **payload: Any,
    ) -> None:
        changes = self._apply_update_changes(
            payload=payload,
            allowed_fields=self._ALLOWED_UPDATE_FIELDS,
        )

        if points is not None:
            old_points = self._points_snapshot(self.points)
            new_points = self._points_snapshot(points)
            if old_points != new_points:
                self.points = points
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
        points: list["DeliveryDocumentPoint"],
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


class DeliveryDocumentPoint(BaseEntity):
    __tablename__ = "points"

    UQ_DOCUMENT_CLIENT = "points_delivery_document_id_client_id_key"

    __table_args__ = (
        UniqueConstraint(
            "delivery_document_id",
            "client_id",
            name=UQ_DOCUMENT_CLIENT,
        ),
        UniqueConstraint(
            "delivery_document_id",
            "position",
            name="points_delivery_document_id_position_key",
        ),
        CheckConstraint("position >= 0", name="points_position_check"),
    )

    point_id: Mapped[UUID] = mapped_column(primary_key=True)
    delivery_document_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "delivery_documents.delivery_document_id",
            ondelete="CASCADE",
        ),
    )
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.client_id"))
    position: Mapped[int] = mapped_column(Integer)

    delivery_document: Mapped[DeliveryDocument] = relationship(
        back_populates="points",
    )
    client: Mapped[Client] = relationship(lazy="joined")
    items: Mapped[list["DeliveryDocumentItem"]] = relationship(
        back_populates="point",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

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
        client_id: UUID,
        position: int,
        items: list["DeliveryDocumentItem"],
        point_id: UUID | None = None,
    ) -> Self:
        return cls(
            point_id=point_id or uuid7(),
            client_id=client_id,
            position=position,
            items=items,
        )


class DeliveryDocumentItem(BaseEntity):
    __tablename__ = "delivery_document_items"

    __table_args__ = (
        CheckConstraint("quantity > 0", name="delivery_document_items_quantity_check"),
        CheckConstraint("price >= 0", name="delivery_document_items_price_check"),
    )

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

    point: Mapped[DeliveryDocumentPoint] = relationship(back_populates="items")
    product: Mapped[Product] = relationship(lazy="joined")

    @property
    def product_name(self) -> str:
        return self.product.name

    @classmethod
    def create(
        cls,
        *,
        product_id: UUID,
        quantity: int,
        price: float = 0,
    ) -> Self:
        return cls(
            product_id=product_id,
            quantity=quantity,
            price=price,
        )


class DeliveryDocumentEditLock(BaseEntity):
    __tablename__ = "delivery_document_edit_locks"

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
