from dataclasses import dataclass
from uuid import UUID

from src.app.cars.abcs.uow import ICarsUOW
from src.domain.cars.entities import Car
from src.domain.cars.car_excs import (
    CarNotFoundException,
    CarNumberAlreadyExistsException,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class UpdateCarDTO:
    actor_id: UUID
    car_id: UUID
    model: str | None = None
    number: str | None = None
    current_mileage: float | None = None


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

            if dto.number is not None and dto.number != car.number:
                existing = await uow.cars.get_by_number(dto.number)

                if existing is not None:
                    raise CarNumberAlreadyExistsException(
                        number=dto.number,
                    )

            car.update(
                actor_id=dto.actor_id,
                model=dto.model,
                number=dto.number,
                current_mileage=dto.current_mileage,
            )

            await uow.cars.update(car)

            await uow.commit(
                events=car.pull_events(),
            )

            return car