import pytest
from src.core.uuid7 import uuid7

from src.common.infra.services.event_pud_service import EventPublisher
from src.feat.employees.domain.employee_events import CreateEmployeeEvent


@pytest.mark.integration
async def test_publish_many_saves_events(postgres) -> None:
    publisher = EventPublisher(
        session_factory=postgres.session_factory,
    )

    actor_id = uuid7()
    employee_id = uuid7()

    event = CreateEmployeeEvent(
        actor_id=actor_id,
        employee_id=employee_id,
    )

    await publisher.publish_many(
        events=[event],
    )

    await publisher.wait_pending()

    async with postgres.session_factory() as session:
        from src.common.infra.db.postgres.repos.events.repo import EventsRepository

        repository = EventsRepository(
            session=session,
        )

        result = await repository.get_all(
            offset=0,
            limit=100,
        )

    saved = next(item for item in result if item.payload.get("employee_id") == str(employee_id))

    assert saved.event_type == "CreateEmployeeEvent"
    assert saved.actor_id == actor_id
    assert saved.payload["actor_id"] == str(actor_id)
    assert saved.payload["employee_id"] == str(employee_id)
