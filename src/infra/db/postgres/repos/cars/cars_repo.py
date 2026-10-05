from uuid import UUID

from asyncpg import exceptions as pg_excs
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.cars.abcs.cars_repo import ICarsRepository
from src.domain.cars.car_excs import CarNumberAlreadyExistsException
from src.domain.cars.entities import Car


class CarsRepository(ICarsRepository):
    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._session = session

    async def add(
        self,
        car: Car,
    ) -> None:
        self._session.add(car)

    async def update(self, car: Car) -> None:
        number = car.number
        try:
            await self._session.flush()
        except IntegrityError as exc:
            pgcode = getattr(exc.orig, "pgcode", None)
            # Проверяем код по официальной константе и имя констрейнта в тексте ошибки
            if pgcode == pg_excs.UniqueViolationError.sqlstate and car.UQ_NUMBER in str(
                exc.orig
            ):
                raise CarNumberAlreadyExistsException(number=number) from exc

            raise

    async def get_by_id(
        self,
        car_id: UUID,
    ) -> Car | None:
        stmt = select(Car).where(
            Car.car_id == car_id,
        )

        result = await self._session.execute(stmt)

        return result.scalar_one_or_none()

    async def get_by_number(
        self,
        number: str,
    ) -> Car | None:
        stmt = select(Car).where(
            Car.number == number,
        )

        result = await self._session.execute(stmt)

        return result.scalar_one_or_none()

    async def get_all(
        self,
        include_deactivated: bool = False,
    ) -> list[Car]:
        stmt = select(Car)

        if not include_deactivated:
            stmt = stmt.where(
                Car.is_active.is_(True),
            )

        stmt = stmt.order_by(Car.model, Car.number)

        result = await self._session.execute(stmt)

        return list(result.scalars().all())
