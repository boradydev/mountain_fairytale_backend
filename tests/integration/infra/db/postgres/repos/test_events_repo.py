from datetime import datetime

import pytest
from uuid6 import uuid7

from src.domain.common.event_record import EventRecord
from src.infra.db.postgres.repos.events.repo import EventsRepository


@pytest.mark.integration
async def test_add_many_and_get_all(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = EventsRepository(
            session=session,
        )

        actor_id = uuid7()

        first = EventRecord(
            event_id=uuid7(),
            event_type="CreateEmployeeEvent",
            actor_id=actor_id,
            created_at=datetime.now(),
            payload={
                "employee_id": str(uuid7()),
            },
        )

        second = EventRecord(
            event_id=uuid7(),
            event_type="UpdateEmployeeEvent",
            actor_id=actor_id,
            created_at=datetime.now(),
            payload={
                "employee_id": str(uuid7()),
                "changes": {
                    "username": {
                        "old": "alex",
                        "new": "alexander",
                    },
                },
            },
        )

        await repository.add_many(
            records=[
                first,
                second,
            ],
        )

        await session.commit()

        result = await repository.get_all(
            offset=0,
            limit=100,
        )

        event_ids = {event.event_id for event in result}

        assert first.event_id in event_ids
        assert second.event_id in event_ids


@pytest.mark.integration
async def test_get_all_pagination(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = EventsRepository(
            session=session,
        )

        records = [
            EventRecord(
                event_id=uuid7(),
                event_type="TestEvent",
                actor_id=uuid7(),
                created_at=datetime.now(),
                payload={
                    "index": index,
                },
            )
            for index in range(3)
        ]

        await repository.add_many(
            records=records,
        )

        await session.commit()

        result = await repository.get_all(
            offset=0,
            limit=2,
        )

        assert len(result) == 2
