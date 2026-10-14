# src/infra/services/event_publisher/password_service.py
import logging
from dataclasses import fields, is_dataclass, replace
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.app.abcs.event_pub_service_abcs import IEventPublisher
from src.common.domain.event_record import EventRecord
from src.common.domain.events import BaseDomainEvent
from src.common.infra.db.postgres.repos.events.event_repos import EventsRepository
from src.core.uuid7 import uuid7
from src.feat.clients.domain.client_entities import Client


logger = logging.getLogger(__name__)


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
            prepared = []
            for event in events:
                if event.subject_type == "delivery_point" and type(event).__name__.startswith("Create") and event.data:
                    client_id = event.data.get("client_id")
                    name = await self._session.scalar(select(Client.name).where(Client.client_id == client_id))
                    event = replace(event, data={**event.data, "display_name": name or str(client_id)})
                prepared.append(event)
            records = [self._to_record(event, operation_id=operation_id) for event in prepared]

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
