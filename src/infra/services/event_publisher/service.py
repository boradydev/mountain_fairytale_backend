# src/infra/services/event_publisher/service.py
import logging
from dataclasses import fields, is_dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from src.core.uuid7 import uuid7

from src.app.common.abcs.services.event_publisher import IEventPublisher
from src.domain.common.event_record import EventRecord
from src.domain.common.events import BaseDomainEvent
from src.infra.db.postgres.repos.events.repo import EventsRepository


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
            records = [self._to_record(event) for event in events]

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
    ) -> EventRecord:
        payload = EventPublisher._serialize_event(event)

        return EventRecord(
            event_id=uuid7(),
            event_type=type(event).__name__,
            actor_id=event.actor_id,
            created_at=event.created_at,
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

        if is_dataclass(value):
            return {
                field.name: EventPublisher._serialize_value(
                    getattr(value, field.name),
                )
                for field in fields(value)
            }

        if isinstance(value, dict):
            return {str(key): EventPublisher._serialize_value(item) for key, item in value.items()}

        if isinstance(value, (list, tuple)):
            return [EventPublisher._serialize_value(item) for item in value]

        return value
