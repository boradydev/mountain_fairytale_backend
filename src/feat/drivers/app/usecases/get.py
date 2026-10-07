from dataclasses import dataclass
from uuid import UUID

from src.feat.drivers.app.abcs.driver_uow_abcs import IDriversUOW
from src.domain.drivers.driver_entities import Driver
from src.feat.drivers.domain.driver_excs import DriverNotFoundException


@dataclass(frozen=True, slots=True, kw_only=True)
class GetDriverDTO:
    driver_id: UUID


class GetDriverUseCase:
    def __init__(
        self,
        uow: IDriversUOW,
    ) -> None:
        self._uow = uow

    async def execute(
        self,
        dto: GetDriverDTO,
    ) -> Driver:
        async with self._uow as uow:
            driver = await uow.drivers.get_by_id(dto.driver_id)

            if driver is None:
                raise DriverNotFoundException(
                    driver_id=dto.driver_id,
                )

            return driver
