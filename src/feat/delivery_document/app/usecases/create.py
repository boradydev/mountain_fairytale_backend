import hashlib
import json
from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID

from src.feat.delivery_document.app.abcs.delivery_document_uow_abcs import IDeliveryDocumentsUOW
from src.feat.delivery_document.domain.delivery_document_entities import DeliveryDocument
from src.feat.delivery_document.domain.delivery_document_excs import DeliveryDocumentUpdateException


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateDeliveryDocumentDTO:
    actor_id: UUID
    document_type: str
    planned_date: date
    points: list[Any]
    creation_request_id: UUID | None = None
    driver_id: UUID | None = None
    car_id: UUID | None = None
    start_mileage: float | None = None
    end_mileage: float | None = None


class CreateDeliveryDocumentUseCase:
    def __init__(self, uow: IDeliveryDocumentsUOW) -> None:
        self._uow = uow

    async def execute(self, dto: CreateDeliveryDocumentDTO) -> DeliveryDocument:
        async with self._uow as uow:
            request_hash = (
                None
                if dto.creation_request_id is None
                else hashlib.sha256(
                    json.dumps(
                        {
                            "type": dto.document_type,
                            "date": dto.planned_date.isoformat(),
                            "driver": str(dto.driver_id),
                            "car": str(dto.car_id),
                            "start": dto.start_mileage,
                            "end": dto.end_mileage,
                            "points": [
                                {
                                    "client": str(point.client_id),
                                    "items": [
                                        {
                                            "id": str(item.product_id),
                                            "name": item.product_name,
                                            "quantity": item.quantity,
                                            "price": str(item.price.normalize()),
                                        }
                                        for item in point.items
                                    ],
                                }
                                for point in dto.points
                            ],
                        },
                        sort_keys=True,
                        ensure_ascii=True,
                    ).encode()
                ).hexdigest()
            )
            if dto.creation_request_id is not None:
                existing = await uow.delivery_documents.get_by_creation_request(
                    dto.creation_request_id, document_type=dto.document_type
                )
                if existing is not None:
                    if existing.creation_request_hash != request_hash:
                        raise DeliveryDocumentUpdateException(
                            field="creation_request_id",
                            message="Creation request was already used with different data.",
                        )
                    return existing
            await uow.delivery_documents.validate_active_assignments(
                document_type=dto.document_type,
                planned_date=dto.planned_date,
                driver_id=dto.driver_id,
                car_id=dto.car_id,
            )
            document = DeliveryDocument.create(
                actor_id=dto.actor_id,
                document_type=dto.document_type,
                planned_date=dto.planned_date,
                points=dto.points,
                driver_id=dto.driver_id,
                car_id=dto.car_id,
                start_mileage=dto.start_mileage,
                end_mileage=dto.end_mileage,
            )
            document.creation_request_id = dto.creation_request_id
            document.creation_request_hash = request_hash if dto.creation_request_id is not None else None
            document.last_operation_id = dto.creation_request_id
            await uow.delivery_documents.validate_references(document)
            await uow.delivery_documents.capture_commissions(document, is_new=True)
            car_events = await uow.delivery_documents.sync_car_mileage(document, actor_id=dto.actor_id)
            await uow.delivery_documents.add(document)
            events = document.pull_aggregate_events() + car_events
            loaded = await uow.delivery_documents.get_by_id(
                document.delivery_document_id,
                document_type=document.document_type,
            )
            await uow.commit(events=events)
            return loaded or document
