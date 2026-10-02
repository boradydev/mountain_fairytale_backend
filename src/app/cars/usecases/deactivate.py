from dataclasses import dataclass
from uuid import UUID

from src.app.cars.abcs.uow import ICarsUOW
from src.domain.cars.excs import CarNotFoundException


@dataclass(frozen=True, slots=True, kw_only=True)
class DeactivateCarDTO:
    actor_id: UUID
    car_id: UUID


class DeactivateCarUseCase:
    def __init__(
        self,
        uow: ICarsUOW,
    ) -> None:
        self._uow = uow

    async def execute(
        self,
        dto: DeactivateCarDTO,
    ) -> None:
        async with self._uow as uow:
            car = await uow.cars.get_by_id(dto.car_id)

            if car is None:
                raise CarNotFoundException(
                    car_id=dto.car_id,
                )

            car.deactivate(
                actor_id=dto.actor_id,
            )

            await uow.cars.update(car)

            await uow.commit(
                events=car.pull_events(),
            )
