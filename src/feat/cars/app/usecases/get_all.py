from dataclasses import dataclass

from src.feat.cars.app.abcs.car_uow_abcs import ICarsUOW
from src.feat.cars.domain.car_entities import Car


@dataclass(frozen=True, slots=True, kw_only=True)
class GetCarsDTO:
    include_deactivated: bool


class GetCarsUseCase:
    def __init__(
        self,
        uow: ICarsUOW,
    ) -> None:
        self._uow = uow

    async def execute(
        self,
        dto: GetCarsDTO,
    ) -> list[Car]:
        async with self._uow as uow:
            return await uow.cars.get_all(include_deactivated=dto.include_deactivated)
