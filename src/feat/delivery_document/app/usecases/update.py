from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from src.feat.delivery_document.api.delivery_document_schemas import (
    UpdateDeliveryRouteSheetReq,
    UpdatePickupSheetReq,
)
from src.feat.delivery_document.app.abcs.delivery_document_uow_abcs import (
    IDeliveryDocumentsUOW,
)
from src.feat.delivery_document.app.usecases._helpers import (
    update_event_changes,
    update_points,
)
from src.feat.delivery_document.domain.delivery_document_entities import (
    DeliveryDocument,
)
from src.feat.delivery_document.domain.delivery_document_excs import (
    DeliveryDocumentEditLockNotFoundException,
    DeliveryDocumentEditLockNotOwnedException,
    DeliveryDocumentNotFoundException,
    DeliveryDocumentUpdateException,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class UpdateDeliveryDocumentDTO:
    actor_id: UUID
    delivery_document_id: UUID
    document_type: str
    payload: UpdateDeliveryRouteSheetReq | UpdatePickupSheetReq


class UpdateDeliveryDocumentUseCase:
    def __init__(self, uow: IDeliveryDocumentsUOW) -> None:
        self._uow = uow

    async def execute(self, dto: UpdateDeliveryDocumentDTO) -> DeliveryDocument:
        async with self._uow as uow:
            document = await uow.delivery_documents.get_by_id(
                dto.delivery_document_id,
                document_type=dto.document_type,
            )
            if document is None:
                raise DeliveryDocumentNotFoundException(
                    delivery_document_id=dto.delivery_document_id,
                )

            if not document.is_active:
                raise DeliveryDocumentUpdateException(
                    field="is_active",
                    message="A cancelled document cannot be edited.",
                )

            await self._ensure_edit_lock(
                uow=uow,
                delivery_document_id=dto.delivery_document_id,
                employee_id=dto.actor_id,
            )

            values = dto.payload.model_dump(
                exclude_unset=True,
                exclude={"points"},
            )

            resulting_start = values.get("start_mileage", document.start_mileage)
            resulting_end = values.get("end_mileage", document.end_mileage)
            if (
                resulting_start is not None
                and resulting_end is not None
                and resulting_end <= resulting_start
            ):
                raise DeliveryDocumentUpdateException(
                    field="end_mileage",
                    message="End mileage must be greater than start mileage.",
                )

            requested_points = getattr(dto.payload, "points", None)
            point_changes = None
            if "points" in dto.payload.model_fields_set and requested_points is not None:
                point_changes = update_points(
                    document=document,
                    requested_points=requested_points,
                )

            document.update(
                actor_id=dto.actor_id,
                **values,
            )
            update_event_changes(
                document=document,
                actor_id=dto.actor_id,
                point_changes=point_changes,
            )

            await uow.delivery_documents.update(document)
            await uow.commit(events=document.pull_events())
            return document

    @staticmethod
    async def _ensure_edit_lock(
        *,
        uow: IDeliveryDocumentsUOW,
        delivery_document_id: UUID,
        employee_id: UUID,
    ) -> None:
        lock = await uow.delivery_documents.get_edit_lock(delivery_document_id)
        now = datetime.now(UTC).replace(tzinfo=None)

        if lock is None or lock.expires_at <= now:
            raise DeliveryDocumentEditLockNotFoundException(
                delivery_document_id=delivery_document_id,
            )

        if lock.employee_id != employee_id:
            raise DeliveryDocumentEditLockNotOwnedException(
                delivery_document_id=delivery_document_id,
            )
