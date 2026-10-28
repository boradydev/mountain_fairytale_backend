from dataclasses import dataclass
from typing import Any
from uuid import UUID

from src.feat.delivery_document.app.abcs.delivery_document_uow_abcs import IDeliveryDocumentsUOW
from src.feat.delivery_document.domain.delivery_document_entities import DeliveryDocument
from src.feat.delivery_document.domain.delivery_document_excs import (
    DeliveryDocumentEditLockNotFoundException,
    DeliveryDocumentLockedException,
    DeliveryDocumentNotFoundException,
    DeliveryDocumentRevisionConflictException,
    DeliveryDocumentUpdateException,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class UpdateDeliveryDocumentDTO:
    actor_id: UUID
    delivery_document_id: UUID
    document_type: str
    payload: Any


class UpdateDeliveryDocumentUseCase:
    def __init__(self, uow: IDeliveryDocumentsUOW) -> None:
        self._uow = uow

    async def execute(self, dto: UpdateDeliveryDocumentDTO) -> DeliveryDocument:
        async with self._uow as uow:
            repo = uow.delivery_documents
            document = await repo.get_by_id(
                dto.delivery_document_id,
                document_type=dto.document_type,
                for_update=True,
            )
            if document is None:
                raise DeliveryDocumentNotFoundException(delivery_document_id=dto.delivery_document_id)
            if dto.payload.expected_revision != document.revision:
                raise DeliveryDocumentRevisionConflictException(current_revision=document.revision)
            if not document.is_active:
                raise DeliveryDocumentUpdateException(
                    field="is_active", message="Restore the document before editing it."
                )
            lock = await repo.get_edit_lock(dto.delivery_document_id)
            if lock is None:
                raise DeliveryDocumentEditLockNotFoundException(
                    delivery_document_id=dto.delivery_document_id,
                )
            if lock.employee_id != dto.actor_id:
                raise DeliveryDocumentLockedException(
                    delivery_document_id=dto.delivery_document_id,
                    owner_name=lock.owner_name,
                )
            previous_assignment = (document.planned_date, document.driver_id, document.car_id)
            previous_car_id = document.car_id
            previous_end_mileage = document.end_mileage
            payload = dto.payload.changes()
            car_changed = "car_id" in payload and payload["car_id"] != previous_car_id
            correction = payload.get("previous_car_mileage")
            confirmed = payload.get("car_change_confirmed") is True
            if car_changed:
                if not {"start_mileage", "end_mileage"} <= payload.keys():
                    raise DeliveryDocumentUpdateException(
                        field="car_id", message="Supply new start and end mileage when replacing a car."
                    )
                if previous_end_mileage is not None and not confirmed:
                    raise DeliveryDocumentUpdateException(
                        field="car_id", message="Confirm car replacement after recorded end mileage."
                    )
            if correction is not None and not (car_changed and previous_end_mileage is not None and confirmed):
                raise DeliveryDocumentUpdateException(
                    field="previous_car_mileage",
                    message="Mileage correction requires a confirmed recorded car replacement.",
                )
            before = document.snapshot()
            document.update(actor_id=dto.actor_id, request=dto.payload)
            if document.snapshot() != before:
                document.revision += 1
            document.last_operation_id = dto.payload.operation_id
            if previous_assignment != (document.planned_date, document.driver_id, document.car_id):
                await repo.validate_active_assignments(
                    document_type=document.document_type,
                    planned_date=document.planned_date,
                    driver_id=document.driver_id,
                    car_id=document.car_id,
                )
            await repo.validate_references(document)
            await repo.capture_commissions(document, is_new=False)
            car_events = await repo.sync_car_mileage(
                document,
                actor_id=dto.actor_id,
                previous_car_id=previous_car_id,
                previous_end_mileage=previous_end_mileage,
                previous_car_mileage=correction,
            )
            await repo.update(document)
            events = document.pull_aggregate_events() + car_events
            loaded = await repo.get_by_id(
                document.delivery_document_id,
                document_type=document.document_type,
            )
            await uow.commit(events=events)
            return loaded or document
