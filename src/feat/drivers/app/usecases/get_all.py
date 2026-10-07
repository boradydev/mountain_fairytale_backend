from dataclasses import dataclass

from src.feat.drivers.app.abcs.driver_uow_abcs import IDriversUOW
from src.domain.drivers.driver_entities import Driver


@dataclass(frozen=True, slots=True, kw_only=True)
class GetDriversDTO:
    include_deactivated: bool


class GetDriversUseCase:
    def __init__(
        self,
        uow: IDriversUOW,
    ) -> None:
        self._uow = uow

    async def execute(
        self,
        dto: GetDriversDTO,
    ) -> list[Driver]:
        async with self._uow as uow:
            return await uow.drivers.get_all(
                include_deactivated=dto.include_deactivated,
            )
