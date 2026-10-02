from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.cars.abcs.cars_repo import ICarsRepository
from src.domain.cars.entities import Car
from src.infra.db.postgres.repos.cars.sql.registry import CarSQL


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
        await self._session.execute(
            CarSQL.ADD,
            {
                "car_id": car.car_id,
                "model": car.model,
                "number": car.number,
                "current_mileage": car.current_mileage,
            },
        )

    async def update(
        self,
        car: Car,
    ) -> None:
        changes = car.get_changes()

        if not changes:
            return

        await self._session.execute(
            CarSQL.UPDATE(
                car_id=car.car_id,
                changes=changes,
            ),
        )

        car.clear_changes()

    async def delete(
        self,
        car_id: UUID,
    ) -> None:
        await self._session.execute(
            CarSQL.DELETE,
            {
                "car_id": car_id,
            },
        )

    async def get_by_id(
        self,
        car_id: UUID,
    ) -> Car | None:
        result = await self._session.execute(
            CarSQL.GET_BY_ID,
            {
                "car_id": car_id,
            },
        )

        row = result.mappings().one_or_none()

        if row is None:
            return None

        return Car(
            _car_id=row["car_id"],
            _model=row["model"],
            _number=row["number"],
            _current_mileage=row["current_mileage"],
        )

    async def get_by_number(
        self,
        number: str,
    ) -> Car | None:
        result = await self._session.execute(
            CarSQL.GET_BY_NUMBER,
            {
                "number": number,
            },
        )

        row = result.mappings().one_or_none()

        if row is None:
            return None

        return Car(
            _car_id=row["car_id"],
            _model=row["model"],
            _number=row["number"],
            _current_mileage=row["current_mileage"],
        )

    async def get_all(self) -> list[Car]:
        result = await self._session.execute(
            CarSQL.GET_ALL,
        )

        rows = result.mappings().all()

        return [
            Car(
                _car_id=row["car_id"],
                _model=row["model"],
                _number=row["number"],
                _current_mileage=row["current_mileage"],
            )
            for row in rows
        ]