from datetime import datetime, timedelta

import pytest
from collections.abc import AsyncGenerator
from typing import Any

from src.common.domain.event_record import EventRecord
from src.common.infra.db.postgres.repos.events.repo import EventsRepository
from src.core.uuid7 import uuid7


def make_event(index: int, created_at: datetime | None = None) -> EventRecord:
    return EventRecord(
        event_id=uuid7(),
        event_type="TestEvent",
        actor_id=uuid7(),
        created_at=created_at or datetime.now(),
        payload={"index": index},
    )


@pytest.fixture(autouse=True)
async def clean_events_table(postgres) -> AsyncGenerator[None, Any]:
    """Автоматически очищает таблицу событий перед каждым тестом в модуле."""
    await postgres.execute("TRUNCATE TABLE events RESTART IDENTITY CASCADE;")

    yield
    pass


@pytest.mark.integration
async def test_add_many_and_get_all(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = EventsRepository(session=session)

        first = make_event(1)
        second = make_event(2)

        await repository.add_many(
            records=[first, second],
        )
        await session.commit()

        result = await repository.get_all(
            offset=0,
            limit=100,
        )

        result_ids = {event.event_id for event in result}

        assert result_ids == {
            first.event_id,
            second.event_id,
        }


@pytest.mark.integration
async def test_get_all_pagination(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = EventsRepository(session=session)

        records = [make_event(index) for index in range(3)]

        await repository.add_many(records=records)
        await session.commit()

        first_page = await repository.get_all(
            offset=0,
            limit=2,
        )
        second_page = await repository.get_all(
            offset=2,
            limit=2,
        )

        assert len(first_page) == 2
        assert len(second_page) == 1

        first_ids = {event.event_id for event in first_page}
        second_ids = {event.event_id for event in second_page}

        assert first_ids.isdisjoint(second_ids)
        assert first_ids | second_ids == {record.event_id for record in records}


@pytest.mark.integration
async def test_get_all_offset_out_of_range_returns_empty(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = EventsRepository(session=session)

        records = [
            make_event(1),
            make_event(2),
        ]

        await repository.add_many(records=records)
        await session.commit()

        result = await repository.get_all(
            offset=10,
            limit=10,
        )

        assert result == []


@pytest.mark.integration
async def test_get_all_respects_limit(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = EventsRepository(session=session)

        records = [make_event(index) for index in range(5)]

        await repository.add_many(records=records)
        await session.commit()

        result = await repository.get_all(
            offset=0,
            limit=3,
        )

        assert len(result) == 3


@pytest.mark.integration
async def test_get_all_respects_offset(postgres) -> None:
    async with postgres.session_factory() as session:
        repository = EventsRepository(session=session)

        created_at = datetime.now()

        records = [
            make_event(
                index=index,
                created_at=created_at + timedelta(seconds=index),
            )
            for index in range(4)
        ]

        await repository.add_many(records=records)
        await session.commit()

        result = await repository.get_all(
            offset=2,
            limit=10,
        )

        result_ids = {event.event_id for event in result}

        assert result_ids == {
            records[2].event_id,
            records[3].event_id,
        }
