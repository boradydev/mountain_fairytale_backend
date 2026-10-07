from dataclasses import dataclass
from uuid import UUID

from src.app.drivers.abcs.uow import IDriversUOW
from src.domain.drivers.driver_entities import Driver


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateDriverDTO:
    actor_id: UUID
    name: str


class CreateDriverUseCase:
    def __init__(
        self,
        uow: IDriversUOW,
    ) -> None:
        self._uow = uow

    async def execute(
        self,
        dto: CreateDriverDTO,
    ) -> Driver:
        async with self._uow as uow:
            driver = Driver.create(
                actor_id=dto.actor_id,
                name=dto.name,
            )

            await uow.drivers.add(driver)

            await uow.commit(
                events=driver.pull_events(),
            )

            return driver
