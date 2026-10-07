from uuid import UUID

from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.drivers.abcs.drivers_repo_abcs import IDriversRepository
from src.domain.drivers.driver_entities import Driver


class DriversRepository(IDriversRepository):
    _FUZZY_THRESHOLD = 0.35

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._session = session

    async def add(self, driver: Driver) -> None:
        self._session.add(driver)
        await self._session.flush()

    async def update(self, driver: Driver) -> None:
        await self._session.flush()

    async def get_by_id(self, driver_id: UUID) -> Driver | None:
        stmt = select(Driver).where(
            Driver.driver_id == driver_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(self, include_deactivated: bool) -> list[Driver]:
        stmt = select(Driver)
        if not include_deactivated:
            stmt = stmt.where(
                Driver.is_active.is_(True),
            )
        stmt = stmt.order_by(desc(Driver.created_at))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def search_by_fuzzy(self, name: str) -> Driver | None:
        await self._session.execute(
            select(func.set_config(
                "pg_trgm.similarity_threshold",
                str(self._FUZZY_THRESHOLD),
                True,
            )),
        )

        similarity = func.similarity(Driver.name, name)
        length_delta = func.abs(func.length(Driver.name) - len(name))
        stmt = (
            select(Driver)
            .where(
                Driver.name.bool_op("%")(name),
                similarity >= self._FUZZY_THRESHOLD,
            )
            .order_by(
                similarity.desc(),
                length_delta.asc(),
                Driver.created_at.desc(),
                Driver.driver_id.desc(),
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
