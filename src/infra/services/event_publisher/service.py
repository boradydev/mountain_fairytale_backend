import asyncio
import logging
from dataclasses import fields, is_dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from uuid6 import uuid7

from src.app.common.abcs.services.event_publisher import IEventPublisher
from src.domain.common.event_record import EventRecord
from src.domain.common.events import BaseDomainEvent
from src.infra.db.postgres.repos.events.repo import EventsRepository


logger = logging.getLogger(__name__)


class EventPublisher(IEventPublisher):
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._session_factory = session_factory
        self._tasks: set[asyncio.Task[None]] = set()

    async def publish_many(
        self,
        *,
        events: list[BaseDomainEvent],
    ) -> None:
        if not events:
            return

        task = asyncio.create_task(
            self._save_events(events),
        )

        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def wait_pending(self) -> None:
        """Ожидает завершения всех фоновых задач сохранения событий."""
        if not self._tasks:
            return

        await asyncio.gather(
            *self._tasks,
        )

    async def _save_events(
        self,
        events: list[BaseDomainEvent],
    ) -> None:
        try:
            records = [self._to_record(event) for event in events]

            async with self._session_factory() as session:
                repository = EventsRepository(
                    session=session,
                )

                await repository.add_many(
                    records=records,
                )

                await session.commit()

        except Exception:
            logger.exception(
                "Failed to save domain events.",
            )

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
