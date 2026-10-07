from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.drivers.usecases.check_duplicate import CheckDriverDuplicateUseCase
from src.app.drivers.usecases.create import CreateDriverUseCase
from src.app.drivers.usecases.get import GetDriverUseCase
from src.app.drivers.usecases.get_all import GetDriversUseCase
from src.app.drivers.usecases.update import UpdateDriverUseCase
from src.infra.db.postgres.uow.drivers import DriversUOW


class DriversUseCaseFactory:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._session_factory = session_factory

    def create_driver(self) -> CreateDriverUseCase:
        return CreateDriverUseCase(
            uow=self._create_uow(),
        )

    def get_driver(self) -> GetDriverUseCase:
        return GetDriverUseCase(
            uow=self._create_uow(),
        )

    def get_drivers(self) -> GetDriversUseCase:
        return GetDriversUseCase(
            uow=self._create_uow(),
        )

    def update_driver(self) -> UpdateDriverUseCase:
        return UpdateDriverUseCase(
            uow=self._create_uow(),
        )

    def check_duplicate(self) -> CheckDriverDuplicateUseCase:
        return CheckDriverDuplicateUseCase(
            uow=self._create_uow(),
        )

    def _create_uow(self) -> DriversUOW:
        return DriversUOW(
            session_factory=self._session_factory,
        )

    @property
    def create_uow(self) -> DriversUOW:
        return self._create_uow()
