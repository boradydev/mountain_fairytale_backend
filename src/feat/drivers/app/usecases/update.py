from dataclasses import dataclass
from uuid import UUID

from src.feat.drivers.api.driver_schemas import UpdateDriverReq
from src.feat.drivers.app.abcs.driver_uow_abcs import IDriversUOW
from src.feat.drivers.domain.driver_entities import Driver
from src.feat.drivers.domain.driver_excs import DriverNotFoundException


@dataclass(frozen=True, slots=True, kw_only=True)
class UpdateDriverDTO:
    actor_id: UUID
    driver_id: UUID
    payload: UpdateDriverReq


class UpdateDriverUseCase:
    def __init__(
        self,
        uow: IDriversUOW,
    ) -> None:
        self._uow = uow

    async def execute(
        self,
        dto: UpdateDriverDTO,
    ) -> Driver:
        async with self._uow as uow:
            driver = await uow.drivers.get_by_id(dto.driver_id)

            if driver is None:
                raise DriverNotFoundException(
                    driver_id=dto.driver_id,
                )

            driver.update(
                actor_id=dto.actor_id,
                **dto.payload.changes(),
            )

            await uow.drivers.update(driver)

            await uow.commit(
                events=driver.pull_events(),
            )

            return driver
