# src/infra/services/event_publisher/password_service.py
import logging
from dataclasses import fields, is_dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.app.abcs.event_pub_service_abcs import IEventPublisher
from src.common.domain.entities import BaseEntity
from src.common.domain.event_record import EventRecord
from src.common.domain.events import BaseDomainEvent
from src.common.infra.db.postgres.repos.events.event_repos import EventsRepository
from src.core.uuid7 import uuid7
from src.feat.cars.domain.car_entities import Car
from src.feat.clients.domain.client_entities import Client
from src.feat.drivers.domain.driver_entities import Driver
from src.feat.pay_methods.domain.pay_method_entities import PaymentMethod
from src.feat.products.domain.product_entities import Product
from src.feat.sales_rep.domain.sales_rep_entities import SalesRepresentative


logger = logging.getLogger(__name__)


_REFERENCE_FIELDS: dict[str, tuple[type[BaseEntity], str, tuple[str, ...]]] = {
    "sales_representative_id": (SalesRepresentative, "sales_representative_id", ("name",)),
    "default_payment_method_id": (PaymentMethod, "payment_method_id", ("name",)),
    "driver_id": (Driver, "driver_id", ("name",)),
    "car_id": (Car, "car_id", ("model", "number")),
    "client_id": (Client, "client_id", ("name",)),
    "product_id": (Product, "product_id", ("name",)),
}


class EventPublisher(IEventPublisher):
    """
    Публишер доменных событий.

    Создается внутри UOW и использует его сессию.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def publish_many(
        self,
        *,
        events: list[BaseDomainEvent],
    ) -> None:
        if not events:
            return

        try:
            operation_id = uuid7()
            records = [self._to_record(event, operation_id=operation_id) for event in events]
            await self._snapshot_references(records)

            # Передаем внутреннюю сессию в репозиторий событий
            repository = EventsRepository(
                session=self._session,
            )

            await repository.add_many(
                records=records,
            )

        except Exception:
            logger.exception(
                "Failed to save domain events inside transaction.",
            )
            raise

    async def _snapshot_references(self, records: list[EventRecord]) -> None:
        # Обрабатываем только бизнес-значения: actor_id и идентичность события остаются UUID.
        references: dict[str, dict[str, dict[str, Any]]] = {}

        def collect(value: Any, field: str | None = None) -> None:
            if field in _REFERENCE_FIELDS and isinstance(value, str):
                references.setdefault(field, {}).setdefault(value, {"id": value, "display_name": None})
            elif isinstance(value, dict):
                for key, item in value.items():
                    collect(item, field if key in {"old", "new"} else key)
            elif isinstance(value, list):
                for item in value:
                    collect(item, field)

        for record in records:
            collect(record.payload.get("data", {}))
            collect(record.payload.get("changes", {}))

        # Один запрос на справочник для всех старых/новых значений всей операции.
        for field, values in references.items():
            model, id_field, name_fields = _REFERENCE_FIELDS[field]
            id_column = getattr(model, id_field)
            result = await self._session.execute(
                select(id_column, *(getattr(model, name) for name in name_fields)).where(
                    id_column.in_([UUID(value) for value in values])
                )
            )
            for row in result:
                values[str(row[0])]["display_name"] = " ".join(str(part) for part in row[1:] if part is not None)

        def snapshot(value: Any, field: str | None = None) -> Any:
            if field in references and isinstance(value, str):
                return dict(references[field][value])
            if isinstance(value, dict):
                return {key: snapshot(item, field if key in {"old", "new"} else key) for key, item in value.items()}
            if isinstance(value, list):
                return [snapshot(item, field) for item in value]
            return value

        for record in records:
            payload = record.payload
            payload["data"] = snapshot(payload.get("data", {}))
            if "changes" in payload:
                payload["changes"] = snapshot(payload["changes"])
            if payload.get("subject_type") == "delivery_point" and record.event_type.startswith("Create"):
                client = payload["data"].get("client_id")
                if isinstance(client, dict):
                    payload["data"]["display_name"] = client["display_name"] or client["id"]

    @staticmethod
    def _to_record(
        event: BaseDomainEvent,
        *,
        operation_id: UUID | None = None,
    ) -> EventRecord:
        payload = EventPublisher._serialize_event(event)

        return EventRecord(
            event_id=uuid7(),
            operation_id=operation_id or uuid7(),
            event_type=type(event).__name__,
            actor_id=event.actor_id,
            created_at=event.created_at.astimezone(UTC),
            payload=payload,
        )

    @staticmethod
    def _serialize_event(
        event: BaseDomainEvent,
    ) -> dict[str, Any]:
        if not is_dataclass(event):
            raise TypeError(
                f"Event must be a dataclass: {type(event).__name__}",
            )

        return {
            field.name: EventPublisher._serialize_value(
                getattr(event, field.name),
            )
            for field in fields(event)
        }

    @staticmethod
    def _serialize_value(
        value: Any,
    ) -> Any:
        if isinstance(value, Decimal):
            return float(value)

        if isinstance(value, UUID):
            return str(value)

        if isinstance(value, datetime):
            return value.isoformat()

        if isinstance(value, date):
            return value.isoformat()

        if is_dataclass(value):
            return {
                field.name: EventPublisher._serialize_value(
                    getattr(value, field.name),
                )
                for field in fields(value)
            }

        if isinstance(value, dict):
            if set(value) & {"password", "password_hash", "access_token", "refresh_token"}:
                raise ValueError("Sensitive fields are forbidden in audit events")
            return {str(key): EventPublisher._serialize_value(item) for key, item in value.items()}

        if isinstance(value, (list, tuple)):
            return [EventPublisher._serialize_value(item) for item in value]

        return value
