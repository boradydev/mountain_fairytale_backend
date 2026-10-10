from datetime import date, datetime
from typing import Annotated, Self
from uuid import UUID

from pydantic import Field, model_validator

from src.common.api.patch_schema import BasePatchSchema
from src.common.api.schemas import BaseSchema
from src.common.api.types import Mileage, Price, Quantity
from src.feat.delivery_document.domain.delivery_document_entities import (
    DeliveryDocument,
)


class CreateItemReq(BaseSchema):
    product_id: UUID
    quantity: Quantity
    price: Price


class UpdateItemReq(BaseSchema):
    product_id: UUID
    quantity: Quantity


class CreatePointReq(BaseSchema):
    client_id: UUID
    items: Annotated[list[CreateItemReq], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_unique_products(self) -> Self:
        product_ids = [item.product_id for item in self.items]
        if len(product_ids) != len(set(product_ids)):
            raise ValueError("A product can appear only once in a point.")
        return self


class UpdatePointReq(BaseSchema):
    point_id: UUID | None = None
    client_id: UUID
    items: Annotated[list[UpdateItemReq], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_unique_products(self) -> Self:
        product_ids = [item.product_id for item in self.items]
        if len(product_ids) != len(set(product_ids)):
            raise ValueError("A product can appear only once in a point.")
        return self


class CreateDeliveryRouteSheetReq(BaseSchema):
    planned_date: date
    driver_id: UUID
    car_id: UUID
    start_mileage: Mileage
    end_mileage: Mileage | None = None
    points: Annotated[list[CreatePointReq], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        if self.end_mileage is not None and self.end_mileage <= self.start_mileage:
            raise ValueError("End mileage must be greater than start mileage.")
        self._validate_unique_clients(self.points)
        return self

    @staticmethod
    def _validate_unique_clients(
        points: list[CreatePointReq],
    ) -> None:
        client_ids = [point.client_id for point in points]
        if len(client_ids) != len(set(client_ids)):
            raise ValueError("A client can appear only once in a document.")


class CreatePickupSheetReq(BaseSchema):
    planned_date: date
    points: Annotated[list[CreatePointReq], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_unique_clients(self) -> Self:
        client_ids = [point.client_id for point in self.points]
        if len(client_ids) != len(set(client_ids)):
            raise ValueError("A client can appear only once in a document.")
        return self


class UpdateDeliveryRouteSheetReq(BasePatchSchema):
    __entity__ = DeliveryDocument
    __composition_fields__ = {"points"}

    planned_date: date | None = None
    driver_id: UUID | None = None
    car_id: UUID | None = None
    start_mileage: Mileage | None = None
    end_mileage: Mileage | None = None
    points: Annotated[list[UpdatePointReq], Field(min_length=1)] | None = None

    @model_validator(mode="after")
    def validate_patch(self) -> Self:
        non_nullable_fields = (
            "planned_date",
            "driver_id",
            "car_id",
            "start_mileage",
            "points",
        )
        for field_name in non_nullable_fields:
            if (
                field_name in self.model_fields_set
                and getattr(self, field_name) is None
            ):
                raise ValueError(f"Field '{field_name}' cannot be null.")

        if (
            self.start_mileage is not None
            and self.end_mileage is not None
            and self.end_mileage <= self.start_mileage
        ):
            raise ValueError("End mileage must be greater than start mileage.")

        if self.points is not None:
            self._validate_points(self.points)
        return self

    @staticmethod
    def _validate_points(points: list[UpdatePointReq]) -> None:
        client_ids = [point.client_id for point in points]
        if len(client_ids) != len(set(client_ids)):
            raise ValueError("A client can appear only once in a document.")

        point_ids = [point.point_id for point in points if point.point_id is not None]
        if len(point_ids) != len(set(point_ids)):
            raise ValueError("A point ID can appear only once in a document.")


class UpdatePickupSheetReq(BasePatchSchema):
    __entity__ = DeliveryDocument
    __composition_fields__ = {"points"}

    planned_date: date | None = None
    points: Annotated[list[UpdatePointReq], Field(min_length=1)] | None = None

    @model_validator(mode="after")
    def validate_patch(self) -> Self:
        for field_name in ("planned_date", "points"):
            if (
                field_name in self.model_fields_set
                and getattr(self, field_name) is None
            ):
                raise ValueError(f"Field '{field_name}' cannot be null.")

        if self.points is not None:
            UpdateDeliveryRouteSheetReq._validate_points(self.points)
        return self


class ItemResp(BaseSchema):
    product_id: UUID
    product_name: str
    quantity: int
    price: float


class PointResp(BaseSchema):
    point_id: UUID
    client_id: UUID
    client_name: str
    phone: str
    address: str
    default_payment_method_id: UUID | None
    default_payment_method_name: str | None
    sales_representative_id: UUID | None
    sales_representative_name: str | None
    items: list[ItemResp]


class DeliveryRouteSheetResp(BaseSchema):
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
    owner_name: str
