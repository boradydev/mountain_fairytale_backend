from dataclasses import dataclass
from datetime import date
from uuid import UUID

from src.feat.delivery_document.api.delivery_document_schemas import (
    CreateDeliveryDocumentPointReq,
)
from src.feat.delivery_document.app.abcs.delivery_document_uow_abcs import (
    IDeliveryDocumentsUOW,
)
from src.feat.delivery_document.app.usecases._helpers import create_points
from src.feat.delivery_document.domain.delivery_document_entities import (
    DeliveryDocument,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateDeliveryDocumentDTO:
    actor_id: UUID
    planned_date: date
    points: list[CreateDeliveryDocumentPointReq]
    document_type: str
    driver_id: UUID | None = None
    car_id: UUID | None = None
    start_mileage: float | None = None
    end_mileage: float | None = None


class CreateDeliveryDocumentUseCase:
    def __init__(self, uow: IDeliveryDocumentsUOW) -> None:
        self._uow = uow

    async def execute(self, dto: CreateDeliveryDocumentDTO) -> DeliveryDocument:
        async with self._uow as uow:
            document = DeliveryDocument.create(
                actor_id=dto.actor_id,
                document_type=dto.document_type,
                planned_date=dto.planned_date,
                points=create_points(dto.points),
                driver_id=dto.driver_id,
                car_id=dto.car_id,
                start_mileage=dto.start_mileage,
                end_mileage=dto.end_mileage,
            )
            await uow.delivery_documents.add(document)
            await uow.commit(events=document.pull_events())
            return document
