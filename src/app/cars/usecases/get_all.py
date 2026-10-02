from src.app.cars.abcs.uow import ICarsUOW
from src.domain.cars.entities import Car


class GetCarsUseCase:
    def __init__(
        self,
        uow: ICarsUOW,
    ) -> None:
        self._uow = uow

    async def execute(self) -> list[Car]:
        async with self._uow as uow:
            return await uow.cars.get_all()