import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.common.domain.abcs.event_repo_abcs import IEventRepository
from src.common.domain.event_record import AuditRecord, EventRecord
from src.common.infra.db.postgres.repos.events.sql.registry import SQL


class EventsRepository(IEventRepository):
    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._session = session

    async def add_many(
        self,
        records: list[EventRecord],
    ) -> None:
        if not records:
            return

        params = [
            {
                "event_id": record.event_id,
                "operation_id": record.operation_id,
                "event_type": record.event_type,
                "actor_id": record.actor_id,
                "created_at": record.created_at.astimezone(UTC),
                "payload": json.dumps(record.payload),
            }
            for record in records
        ]

        await self._session.execute(
            SQL.ADD_MANY,
            params,
        )

    async def get_all(
        self,
        *,
        offset: int,
        limit: int,
    ) -> list[EventRecord]:
        result = await self._session.execute(
            SQL.GET_ALL,
            {
                "offset": offset,
                "limit": limit,
            },
        )

        rows = result.mappings().all()

        return [
            EventRecord(
                event_id=row["event_id"],
                operation_id=row["operation_id"],
                event_type=row["event_type"],
                actor_id=row["actor_id"],
                created_at=row["created_at"],
                payload=row["payload"],
            )
            for row in rows
        ]

    async def get_page(
        self,
        *,
        search: str,
        before_at: datetime | None,
        before_id: UUID | None,
        limit: int,
        after_at: datetime | None = None,
        after_id: UUID | None = None,
    ) -> list[AuditRecord]:
        result = await self._session.execute(
            SQL.GET_PAGE,
            {
                "search": search,
                "before_at": before_at,
                "before_id": before_id,
                "limit": limit,
                "after_at": after_at,
                "after_id": after_id,
                "newer": after_at is not None,
            },
        )
        return [AuditRecord(**dict(row)) for row in result.mappings().all()]
