from typing import Any
from uuid import UUID

from src.feat.delivery_document.api.delivery_document_schemas import (
    CreateDeliveryDocumentPointReq,
    UpdateDeliveryDocumentPointReq,
)
from src.feat.delivery_document.domain.delivery_document_entities import (
    DeliveryDocument,
    DeliveryDocumentItem,
    DeliveryDocumentPoint,
)
from src.feat.delivery_document.domain.delivery_document_excs import (
    DeliveryDocumentUpdateException,
)


def create_points(
    points: list[CreateDeliveryDocumentPointReq],
) -> list[DeliveryDocumentPoint]:
    return [
        DeliveryDocumentPoint.create(
            client_id=point.client_id,
            position=position,
            items=[
                DeliveryDocumentItem.create(
                    product_id=item.product_id,
                    quantity=item.quantity,
                )
                for item in point.items
            ],
        )
        for position, point in enumerate(points)
    ]


def update_points(
    *,
    document: DeliveryDocument,
    requested_points: list[UpdateDeliveryDocumentPointReq],
) -> dict[str, Any] | None:
    existing_points = {point.point_id: point for point in document.points}
    old_snapshot = DeliveryDocument._points_snapshot(document.points)
    updated_points: list[DeliveryDocumentPoint] = []

    for position, requested_point in enumerate(requested_points):
        if requested_point.point_id is None:
            point = DeliveryDocumentPoint.create(
                client_id=requested_point.client_id,
                position=position,
                items=[
                    DeliveryDocumentItem.create(
                        product_id=item.product_id,
                        quantity=item.quantity,
                    )
                    for item in requested_point.items
                ],
            )
            updated_points.append(point)
            continue

        point = existing_points.get(requested_point.point_id)
        if point is None:
            raise DeliveryDocumentUpdateException(
                field="point_id",
                message="The point does not belong to this document.",
            )

        if point.client_id != requested_point.client_id:
            raise DeliveryDocumentUpdateException(
                field="client_id",
                message="The client of an existing point cannot be changed.",
            )

        point.position = position

        existing_items = {item.product_id: item for item in point.items}
        updated_items: list[DeliveryDocumentItem] = []

        for requested_item in requested_point.items:
            item = existing_items.get(requested_item.product_id)
            if item is None:
                item = DeliveryDocumentItem.create(
                    product_id=requested_item.product_id,
                    quantity=requested_item.quantity,
                )
            else:
                item.quantity = requested_item.quantity
            updated_items.append(item)

        point.items = updated_items
        updated_points.append(point)

    document.points = updated_points
    new_snapshot = DeliveryDocument._points_snapshot(document.points)

    if old_snapshot == new_snapshot:
        return None

    return {
        "old": old_snapshot,
        "new": new_snapshot,
    }


def update_event_changes(
    *,
    document: DeliveryDocument,
    actor_id: UUID,
    point_changes: dict[str, Any] | None,
) -> None:
    if point_changes is None:
        return

    from src.feat.delivery_document.domain.delivery_document_events import (
        UpdateDeliveryDocumentEvent,
    )

    document._add_event(
        UpdateDeliveryDocumentEvent(
            actor_id=actor_id,
            delivery_document_id=document.delivery_document_id,
            changes={"points": point_changes},
        ),
    )
