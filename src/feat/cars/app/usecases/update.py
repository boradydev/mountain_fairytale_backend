from dataclasses import dataclass
from typing import Any
from uuid import UUID

from src.feat.cars.app.abcs.uow import ICarsUOW
from src.feat.cars.domain.car_excs import CarNotFoundException
from src.feat.cars.domain.car_entities import Car


@dataclass(frozen=True, slots=True, kw_only=True)
class UpdateCarDTO:
    actor_id: UUID
    car_id: UUID
    payload: dict[str, Any]


class UpdateCarUseCase:
    def __init__(
        self,
        uow: ICarsUOW,
    ) -> None:
        self._uow = uow

    async def execute(
        self,
        dto: UpdateCarDTO,
    ) -> Car:
        async with self._uow as uow:
            car = await uow.cars.get_by_id(dto.car_id)

            if car is None:
                raise CarNotFoundException(
                    car_id=dto.car_id,
                )

            car.update(
                actor_id=dto.actor_id,
                **dto.payload,
            )

            await uow.cars.update(car)

            await uow.commit(
                events=car.pull_events(),
            )

            return car
