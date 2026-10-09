from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from pydantic import Field, model_validator

from src.common.api.schemas import BaseSchema


Quantity = Annotated[int, Field(gt=0)]
Mileage = Annotated[float, Field(ge=0)]


class CreateDeliveryDocumentItemReq(BaseSchema):
    product_id: UUID
    quantity: Quantity


class UpdateDeliveryDocumentItemReq(BaseSchema):
    product_id: UUID
    quantity: Quantity


class CreateDeliveryDocumentPointReq(BaseSchema):
    client_id: UUID
    items: Annotated[list[CreateDeliveryDocumentItemReq], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_unique_products(self) -> "CreateDeliveryDocumentPointReq":
        product_ids = [item.product_id for item in self.items]
        if len(product_ids) != len(set(product_ids)):
            raise ValueError("A product can appear only once in a point.")
        return self


class UpdateDeliveryDocumentPointReq(BaseSchema):
    point_id: UUID | None = None
    client_id: UUID
    items: Annotated[list[UpdateDeliveryDocumentItemReq], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_unique_products(self) -> "UpdateDeliveryDocumentPointReq":
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
    points: Annotated[list[CreateDeliveryDocumentPointReq], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_request(self) -> "CreateDeliveryRouteSheetReq":
        if self.end_mileage is not None and self.end_mileage <= self.start_mileage:
            raise ValueError("End mileage must be greater than start mileage.")
        self._validate_unique_clients(self.points)
        return self

    @staticmethod
    def _validate_unique_clients(
        points: list[CreateDeliveryDocumentPointReq],
    ) -> None:
        client_ids = [point.client_id for point in points]
        if len(client_ids) != len(set(client_ids)):
            raise ValueError("A client can appear only once in a document.")


class CreatePickupSheetReq(BaseSchema):
    planned_date: date
    points: Annotated[list[CreateDeliveryDocumentPointReq], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_unique_clients(self) -> "CreatePickupSheetReq":
        client_ids = [point.client_id for point in self.points]
        if len(client_ids) != len(set(client_ids)):
            raise ValueError("A client can appear only once in a document.")
        return self


class UpdateDeliveryRouteSheetReq(BaseSchema):
    planned_date: date | None = None
    driver_id: UUID | None = None
    car_id: UUID | None = None
    start_mileage: Mileage | None = None
    end_mileage: Mileage | None = None
    points: Annotated[list[UpdateDeliveryDocumentPointReq], Field(min_length=1)] | None = None

    @model_validator(mode="before")
    @classmethod
    def validate_not_empty(cls, value: object) -> object:
        if isinstance(value, dict) and not value:
            raise ValueError("Request body cannot be empty.")
        return value

    @model_validator(mode="after")
    def validate_patch(self) -> "UpdateDeliveryRouteSheetReq":
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
    def _validate_points(points: list[UpdateDeliveryDocumentPointReq]) -> None:
        client_ids = [point.client_id for point in points]
        if len(client_ids) != len(set(client_ids)):
            raise ValueError("A client can appear only once in a document.")

        point_ids = [point.point_id for point in points if point.point_id is not None]
        if len(point_ids) != len(set(point_ids)):
            raise ValueError("A point ID can appear only once in a document.")


class UpdatePickupSheetReq(BaseSchema):
    planned_date: date | None = None
    points: Annotated[list[UpdateDeliveryDocumentPointReq], Field(min_length=1)] | None = None

    @model_validator(mode="before")
    @classmethod
    def validate_not_empty(cls, value: object) -> object:
        if isinstance(value, dict) and not value:
            raise ValueError("Request body cannot be empty.")
        return value

    @model_validator(mode="after")
    def validate_patch(self) -> "UpdatePickupSheetReq":
        for field_name in ("planned_date", "points"):
            if (
                field_name in self.model_fields_set
                and getattr(self, field_name) is None
            ):
                raise ValueError(f"Field '{field_name}' cannot be null.")

        if self.points is not None:
            UpdateDeliveryRouteSheetReq._validate_points(self.points)
        return self


class DeliveryDocumentItemResp(BaseSchema):
    product_id: UUID
    product_name: str
    quantity: int
    price: float


class DeliveryDocumentPointResp(BaseSchema):
    point_id: UUID
    client_id: UUID
    client_name: str
    phone: str
    address: str
    default_payment_method_id: UUID | None
    default_payment_method_name: str | None
    sales_representative_id: UUID | None
    sales_representative_name: str | None
    items: list[DeliveryDocumentItemResp]


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
    points: list[DeliveryDocumentPointResp]


class PickupSheetResp(BaseSchema):
    delivery_document_id: UUID
    created_at: datetime
    planned_date: date
    is_active: bool
    points: list[DeliveryDocumentPointResp]


class DeliveryRouteSheetsResp(BaseSchema):
    delivery_route_sheets: list[DeliveryRouteSheetResp]


class PickupSheetsResp(BaseSchema):
    pickup_sheets: list[PickupSheetResp]


class DeliveryDocumentEditLockResp(BaseSchema):
    owner_name: str
