from dataclasses import dataclass
from uuid import UUID

from src.app.cars.abcs.uow import ICarsUOW
from src.domain.cars.entities import Car
from src.domain.cars.car_excs import CarNumberAlreadyExistsException


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateCarDTO:
    actor_id: UUID
    model: str
    number: str
    current_mileage: float = 0


class CreateCarUseCase:
    def __init__(
        self,
        uow: ICarsUOW,
    ) -> None:
        self._uow = uow

    async def execute(
        self,
        dto: CreateCarDTO,
    ) -> Car:
        async with self._uow as uow:

            car = Car.create(
                actor_id=dto.actor_id,
                model=dto.model,
                number=dto.number,
                current_mileage=dto.current_mileage,
            )

            await uow.cars.add(car)

            await uow.commit(
                events=car.pull_events(),
            )

            return car