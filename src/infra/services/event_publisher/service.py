from src.app.common.abcs.services.event_publisher import IEventPublisher
from src.domain.common.events import BaseDomainEvent


class EventPublisher(IEventPublisher):
    async def publish_many(
        self,
        *,
        events: list[BaseDomainEvent],
    ) -> None:
        return
