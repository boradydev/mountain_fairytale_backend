from datetime import date, datetime
from typing import Annotated, Self
from uuid import UUID

from pydantic import ConfigDict, Field, model_validator

from src.common.api import fields
from src.common.api.patch_schema import BasePatchSchema
from src.common.api.schemas import BaseSchema
from src.feat.delivery_document.domain.delivery_document_entities import DeliveryDocument


class CreateItemReq(BaseSchema):
    product_id: UUID
    product_name: Annotated[str, Field(min_length=1, max_length=120)]
    quantity: fields.Quantity
    price: fields.Price


class UpdateItemReq(BaseSchema):
    product_id: UUID
    product_name: Annotated[str, Field(min_length=1, max_length=120)]
    quantity: fields.Quantity
    price: fields.Price


class CreatePointReq(BaseSchema):
    is_delivered: bool = True
    non_delivery_reason: Annotated[str, Field(max_length=1000)] = ""
    memo: Annotated[str, Field(max_length=1000)] = ""
    client_id: UUID | None = None
    payment_method_id: UUID | None = Field(
        default=None,
        description="Saved point payment method. Explicit null means unassigned; omitted uses the client default.",
    )
    items: list[CreateItemReq]

    @model_validator(mode="after")
    def validate_unique_products(self) -> Self:
        ids = [item.product_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("A product can appear only once in a point.")
        return self


class UpdatePointReq(BaseSchema):
    is_delivered: bool | None = None
    non_delivery_reason: Annotated[str | None, Field(max_length=1000)] = None
    memo: Annotated[str | None, Field(max_length=1000)] = None
    # Omitted/null point_id means that this is a new point.
    point_id: UUID | None = None
    client_id: UUID | None = None
    payment_method_id: UUID | None = Field(
        default=None,
        description="Explicit UUID/null replaces the point payment method. Omitted preserves existing points; "
        "new points use the client default.",
    )
    items: list[UpdateItemReq]

    @model_validator(mode="after")
    def validate_unique_products(self) -> Self:
        ids = [item.product_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("A product can appear only once in a point.")
        return self


class CreateDeliveryRouteSheetReq(BaseSchema):
    creation_request_id: UUID | None = None
    planned_date: date
    driver_id: UUID
    car_id: UUID
    start_mileage: fields.Mileage
    end_mileage: fields.Mileage | None = None
    points: list[CreatePointReq]

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        _validate_mileage(self.start_mileage, self.end_mileage)
        _validate_unique_clients(self.points)
        return self


class CreatePickupSheetReq(BaseSchema):
    model_config = ConfigDict(extra="forbid")

    creation_request_id: UUID | None = None

    planned_date: date
    points: list[CreatePointReq]

    @model_validator(mode="after")
    def validate_unique_clients(self) -> Self:
        _validate_pickup_clients(self.points)
        return self


class UpdateDeliveryRouteSheetReq(BasePatchSchema):
    __entity__ = DeliveryDocument
    __composition_fields__ = {
        "points",
        "car_change_confirmed",
        "previous_car_mileage",
        "expected_revision",
        "operation_id",
    }

    expected_revision: Annotated[int | None, Field(ge=1)]
    operation_id: UUID | None = None

    planned_date: date | None = None
    driver_id: UUID | None = None
    car_id: UUID | None = None
    start_mileage: fields.Mileage | None = None
    end_mileage: fields.Mileage | None = None
    car_change_confirmed: bool | None = None
    previous_car_mileage: fields.Mileage | None = None
    points: list[UpdatePointReq] | None = None

    @model_validator(mode="after")
    def validate_patch(self) -> Self:
        if self.expected_revision is None:
            raise ValueError("expectedRevision is required.")
        for name in ("planned_date", "driver_id", "car_id", "start_mileage", "points"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"Field '{name}' cannot be null.")
        _validate_mileage(self.start_mileage, self.end_mileage)
        if self.points is not None:
            _validate_patch_points(self.points)
            _validate_unique_clients(self.points)
        return self


class UpdatePickupSheetReq(BasePatchSchema):
    model_config = ConfigDict(extra="forbid")

    __entity__ = DeliveryDocument
    __composition_fields__ = {"points", "expected_revision", "operation_id"}

    expected_revision: Annotated[int | None, Field(ge=1)]
    operation_id: UUID | None = None

    planned_date: date | None = None
    points: list[UpdatePointReq] | None = None

    @model_validator(mode="after")
    def validate_patch(self) -> Self:
        if self.expected_revision is None:
            raise ValueError("expectedRevision is required.")
        for name in ("planned_date", "points"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"Field '{name}' cannot be null.")
        if self.points is not None:
            _validate_patch_points(self.points)
            _validate_pickup_clients(self.points)
        return self


def _validate_mileage(start: float | None, end: float | None) -> None:
    if start is not None and end is not None and end < start:
        raise ValueError("End mileage cannot be less than start mileage.")


def _validate_unique_clients(points: list[CreatePointReq] | list[UpdatePointReq]) -> None:
    client_ids = [point.client_id for point in points]
    if None in client_ids:
        raise ValueError("Delivery points require a client.")
    if len(client_ids) != len(set(client_ids)):
        raise ValueError("A client can appear only once in a document.")


def _validate_patch_points(points: list[UpdatePointReq]) -> None:
    point_ids = [point.point_id for point in points if point.point_id is not None]
    if len(point_ids) != len(set(point_ids)):
        raise ValueError("A point ID can appear only once in a document.")


def _validate_pickup_clients(points: list[CreatePointReq] | list[UpdatePointReq]) -> None:
    if any(point.client_id is not None for point in points):
        raise ValueError("Pickup purchases cannot contain a client.")


class ItemResp(BaseSchema):
    product_id: UUID
    product_name: str
    quantity: int
    price: float


class PointResp(BaseSchema):
    is_delivered: bool
    non_delivery_reason: str
    memo: str
    point_id: UUID
    client_id: UUID | None
    client_name: str
    phone: str
    address: str
    client_address: str
    delivery_details: str
    default_payment_method_id: UUID | None
    default_payment_method_name: str | None
    payment_method_id: UUID | None
    payment_method_name: str | None
    sales_representative_id: UUID | None
    sales_representative_name: str | None
    position: int
    items: list[ItemResp]


class DeliveryRouteSheetResp(BaseSchema):
    revision: int
    last_operation_id: UUID | None
    delivery_document_id: UUID
    created_at: datetime
    planned_date: date
    is_active: bool
    driver_id: UUID
    driver_name: str
    car_id: UUID
    car_model_and_number: str
    start_mileage: float
    end_mileage: float | None
    points: list[PointResp]


class PickupSheetResp(BaseSchema):
    revision: int
    last_operation_id: UUID | None
    delivery_document_id: UUID
    created_at: datetime
    planned_date: date
    is_active: bool
    points: list[PointResp]


class DeliveryRouteSheetsResp(BaseSchema):
    delivery_route_sheets: list[DeliveryRouteSheetResp]


class PickupSheetsResp(BaseSchema):
    pickup_sheets: list[PickupSheetResp]


class DeliveryDocumentEditLockResp(BaseSchema):
    owner_name: str | None
