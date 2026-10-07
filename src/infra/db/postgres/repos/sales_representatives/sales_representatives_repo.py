from uuid import UUID

from asyncpg import exceptions as pg_excs
from sqlalchemy import select, desc, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.sales_representatives.abcs.sales_representatives_repo_abcs import ISalesRepresentativesRepository
from src.domain.sales_representatives.sales_representative_entities import SalesRepresentative
from src.domain.sales_representatives.sales_representative_excs import SalesRepresentativePhoneAlreadyExistsException


class SalesRepresentativesRepository(ISalesRepresentativesRepository):
    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._session = session

    async def add(
        self,
        sales_representative: SalesRepresentative,
    ) -> None:
        self._session.add(sales_representative)
        phone = sales_representative.phone
        try:
            await self._session.flush()
        except IntegrityError as exc:
            pgcode = getattr(exc.orig, "pgcode", None)
            if pgcode == pg_excs.UniqueViolationError.sqlstate and sales_representative.UQ_PHONE in str(exc.orig):
                raise SalesRepresentativePhoneAlreadyExistsException(phone=phone) from exc

            raise

    async def update(self, sales_representative: SalesRepresentative) -> None:
        phone = sales_representative.phone
        try:
            await self._session.flush()
        except IntegrityError as exc:
            pgcode = getattr(exc.orig, "pgcode", None)
            if pgcode == pg_excs.UniqueViolationError.sqlstate and sales_representative.UQ_PHONE in str(exc.orig):
                raise SalesRepresentativePhoneAlreadyExistsException(phone=phone) from exc

            raise

    async def get_by_id(
        self,
        sales_representative_id: UUID,
    ) -> SalesRepresentative | None:
        stmt = select(SalesRepresentative).where(
            SalesRepresentative.sales_representative_id == sales_representative_id,
        )

        result = await self._session.execute(stmt)

        return result.scalar_one_or_none()

    async def get_by_phone(
        self,
        phone: str,
    ) -> SalesRepresentative | None:
        stmt = select(SalesRepresentative).where(
            SalesRepresentative.phone == phone,
        )

        result = await self._session.execute(stmt)

        return result.scalar_one_or_none()

    async def get_all(
        self,
        include_deactivated: bool,
    ) -> list[SalesRepresentative]:
        stmt = select(SalesRepresentative)

        if not include_deactivated:
            stmt = stmt.where(
                SalesRepresentative.is_active.is_(True),
            )

        stmt = stmt.order_by(desc(SalesRepresentative.created_at))

        result = await self._session.execute(stmt)

        return list(result.scalars().all())

    async def search_by_fuzzy(
        self,
        name: str,
        phone: str,
    ) -> SalesRepresentative | None:
        await self._session.execute(
            select(func.set_config(
                "pg_trgm.similarity_threshold",
                "0.349999",
                True,
            )),
        )

        name_sim = func.similarity(SalesRepresentative.name, name)
        phone_sim = func.similarity(SalesRepresentative.phone, phone)
        avg_sim = (name_sim + phone_sim) / 2

        stmt = (
            select(SalesRepresentative)
            .where(
                SalesRepresentative.name.bool_op("%")(name),
                SalesRepresentative.phone.bool_op("%")(phone),
                name_sim >= 0.35,
                phone_sim >= 0.50,
            )
            .order_by(
                avg_sim.desc(),
                desc(SalesRepresentative.created_at),
                desc(SalesRepresentative.sales_representative_id),
            )
            .limit(1)
        )

        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
