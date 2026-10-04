from dataclasses import dataclass
from uuid import UUID

from src.app.cars.abcs.uow import ICarsUOW
from src.domain.cars.car_excs import CarNotFoundException


@dataclass(frozen=True, slots=True, kw_only=True)
class DeleteCarDTO:
    actor_id: UUID
    car_id: UUID


class DeleteCarUseCase:
    def __init__(
        self,
        uow: ICarsUOW,
    ) -> None:
        self._uow = uow

    async def execute(
        self,
        dto: DeleteCarDTO,
    ) -> None:
        async with self._uow as uow:
            car = await uow.cars.get_by_id(dto.car_id)

            if car is None:
                raise CarNotFoundException(
                    car_id=dto.car_id,
                )

            car.delete(
                actor_id=dto.actor_id,
            )

            await uow.cars.delete(
                dto.car_id,
            )

            await uow.commit(
                events=car.pull_events(),
            )