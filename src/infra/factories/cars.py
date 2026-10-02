from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.cars.usecases.activate import ActivateCarUseCase
from src.app.cars.usecases.check_duplicate import CheckCarDuplicateUseCase
from src.app.cars.usecases.create import CreateCarUseCase
from src.app.cars.usecases.deactivate import DeactivateCarUseCase
from src.app.cars.usecases.get import GetCarUseCase
from src.app.cars.usecases.get_all import GetCarsUseCase
from src.app.cars.usecases.update import UpdateCarUseCase
from src.infra.db.postgres.uow.cars import CarsUOW


class CarsUseCaseFactory:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._session_factory = session_factory

    def create_car(self) -> CreateCarUseCase:
        return CreateCarUseCase(
            uow=self._create_uow(),
        )

    def get_car(self) -> GetCarUseCase:
        return GetCarUseCase(
            uow=self._create_uow(),
        )

    def get_cars(self) -> GetCarsUseCase:
        return GetCarsUseCase(
            uow=self._create_uow(),
        )

    def update_car(self) -> UpdateCarUseCase:
        return UpdateCarUseCase(
            uow=self._create_uow(),
        )

    def activate_car(self) -> ActivateCarUseCase:
        return ActivateCarUseCase(
            uow=self._create_uow(),
        )

    def deactivate_car(self) -> DeactivateCarUseCase:
        return DeactivateCarUseCase(
            uow=self._create_uow(),
        )

    def check_duplicate(self) -> CheckCarDuplicateUseCase:
        return CheckCarDuplicateUseCase(
            uow=self._create_uow(),
        )

    def _create_uow(self) -> CarsUOW:
        return CarsUOW(
            session_factory=self._session_factory,
        )

    @property
    def create_uow(self) -> CarsUOW:
        return self._create_uow()
