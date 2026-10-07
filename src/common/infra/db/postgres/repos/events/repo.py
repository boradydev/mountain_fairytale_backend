import json

from sqlalchemy.ext.asyncio import AsyncSession

from src.common.domain.event_record import EventRecord
from src.common.infra.db.postgres.repos.events.sql.registry import SQL


class EventsRepository:
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
                "event_type": record.event_type,
                "actor_id": record.actor_id,
                "created_at": record.created_at,
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
                event_type=row["event_type"],
                actor_id=row["actor_id"],
                created_at=row["created_at"],
                payload=row["payload"],
            )
            for row in rows
        ]
