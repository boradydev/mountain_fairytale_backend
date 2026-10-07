from dataclasses import dataclass

from src.app.drivers.abcs.uow import IDriversUOW
from src.domain.drivers.driver_entities import Driver


@dataclass(frozen=True, slots=True, kw_only=True)
class CheckDriverDuplicateDTO:
    name: str


class CheckDriverDuplicateUseCase:
    def __init__(
        self,
        uow: IDriversUOW,
    ) -> None:
        self._uow = uow

    async def execute(
        self,
        dto: CheckDriverDuplicateDTO,
    ) -> Driver | None:
        async with self._uow as uow:
            return await uow.drivers.search_by_fuzzy(
                dto.name,
            )
