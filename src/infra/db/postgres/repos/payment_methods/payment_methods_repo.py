from uuid import UUID

from asyncpg import exceptions as pg_excs
from sqlalchemy import select, desc, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.payment_methods.abcs.payment_methods_repo_abcs import IPaymentMethodsRepository
from src.domain.payment_methods.payment_method_entities import PaymentMethod
from src.domain.payment_methods.payment_method_excs import PaymentMethodNameAlreadyExistsException


class PaymentMethodsRepository(IPaymentMethodsRepository):
    _FUZZY_THRESHOLD = 0.35

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._session = session

    async def add(self, payment_method: PaymentMethod) -> None:
        self._session.add(payment_method)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            pgcode = getattr(exc.orig, "pgcode", None)
            if pgcode == pg_excs.UniqueViolationError.sqlstate and payment_method.UQ_NAME in str(exc.orig):
                raise PaymentMethodNameAlreadyExistsException() from exc
            raise

    async def update(self, payment_method: PaymentMethod) -> None:
        try:
            await self._session.flush()
        except IntegrityError as exc:
            pgcode = getattr(exc.orig, "pgcode", None)
            if pgcode == pg_excs.UniqueViolationError.sqlstate and payment_method.UQ_NAME in str(exc.orig):
                raise PaymentMethodNameAlreadyExistsException() from exc
            raise

    async def get_by_id(self, payment_method_id: UUID) -> PaymentMethod | None:
        stmt = select(PaymentMethod).where(
            PaymentMethod.payment_method_id == payment_method_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(self, include_deactivated: bool) -> list[PaymentMethod]:
        stmt = select(PaymentMethod)
        if not include_deactivated:
            stmt = stmt.where(
                PaymentMethod.is_active.is_(True),
            )
        stmt = stmt.order_by(desc(PaymentMethod.created_at))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def search_by_fuzzy(self, name: str) -> PaymentMethod | None:
        await self._session.execute(
            select(func.set_config(
                "pg_trgm.similarity_threshold",
                str(self._FUZZY_THRESHOLD),
                True,
            )),
        )

        similarity = func.similarity(PaymentMethod.name, name)
        stmt = (
            select(PaymentMethod)
            .where(
                PaymentMethod.name.bool_op("%")(name),
                similarity >= self._FUZZY_THRESHOLD,
            )
            .order_by(
                similarity.desc(),
                PaymentMethod.created_at.desc(),
                PaymentMethod.payment_method_id.desc(),
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
