from dataclasses import dataclass
from uuid import UUID

from src.app.cars.abcs.uow import ICarsUOW
from src.domain.cars.entities import Car
from src.domain.cars.car_excs import CarNotFoundException


@dataclass(frozen=True, slots=True, kw_only=True)
class GetCarDTO:
    car_id: UUID


class GetCarUseCase:
    def __init__(
        self,
        uow: ICarsUOW,
    ) -> None:
        self._uow = uow

    async def execute(
        self,
        dto: GetCarDTO,
    ) -> Car:
        async with self._uow as uow:
            car = await uow.cars.get_by_id(dto.car_id)

            if car is None:
                raise CarNotFoundException(
                    car_id=dto.car_id,
                )

            return car