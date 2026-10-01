from abc import ABC, abstractmethod

from src.domain.common.events import BaseDomainEvent


class IEventPublisher(ABC):
    """
    Интерфейс брокера событий.

    Отвечает за доставку доменных событий соответствующим подписчикам.
    """

    @abstractmethod
    async def publish_many(
        self,
        *,
        events: list[BaseDomainEvent],
    ) -> None:
        pass
        """
        Оптимизированная публикация списка событий.

        Полезна для вызова из UOW.commit(events=...).
        """
