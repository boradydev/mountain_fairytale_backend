from dataclasses import dataclass

from src.feat.cars.app.abcs.car_uow_abcs import ICarsUOW
from src.feat.cars.domain.car_entities import Car


@dataclass(frozen=True, slots=True, kw_only=True)
class CheckCarDuplicateDTO:
    number: str


class CheckCarDuplicateUseCase:
    def __init__(
        self,
        uow: ICarsUOW,
    ) -> None:
        self._uow = uow

    async def execute(
        self,
        dto: CheckCarDuplicateDTO,
    ) -> Car | None:
        async with self._uow as uow:
            return await uow.cars.get_by_number(
                dto.number,
            )