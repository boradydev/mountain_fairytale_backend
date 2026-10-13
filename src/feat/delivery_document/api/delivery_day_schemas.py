from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from src.common.api.schemas import BaseSchema
from src.feat.delivery_document.api.delivery_document_schemas import DeliveryRouteSheetResp, PickupSheetResp


class DeliveryDayProductResp(BaseSchema):
    product_id: UUID
    product_name: str
    quantity: int


class DeliveryDayResp(BaseSchema):
    planned_date: date
    delivery_points_count: int
    pickup_points_count: int
    products: list[DeliveryDayProductResp]
    total_amount: float


class DeliveryDaysResp(BaseSchema):
    delivery_days: list[DeliveryDayResp]


class DayDeliveryRouteSheetResp(DeliveryRouteSheetResp):
    document_type: Literal["deliveryRouteSheet"]


class DayPickupSheetResp(PickupSheetResp):
    document_type: Literal["pickupSheet"]


type DayDocumentResp = Annotated[DayDeliveryRouteSheetResp | DayPickupSheetResp, Field(discriminator="document_type")]


class DayDocumentsResp(BaseSchema):
    documents: list[DayDocumentResp]
