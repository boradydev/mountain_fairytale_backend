from uuid import UUID

from asyncpg import exceptions as pg_excs
from sqlalchemy import select, desc, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.feat.products.domain.abcs.product_repo_abcs import IProductsRepository
from src.feat.products.domain.product_entities import Product
from src.feat.products.domain.product_excs import ProductNameAlreadyExistsException


class ProductsRepository(IProductsRepository):
    _FUZZY_THRESHOLD = 0.35

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._session = session

    async def add(self, product: Product) -> None:
        self._session.add(product)
        name = product.name
        try:
            await self._session.flush()
        except IntegrityError as exc:
            pgcode = getattr(exc.orig, "pgcode", None)
            if pgcode == pg_excs.UniqueViolationError.sqlstate and product.UQ_NAME in str(exc.orig):
                raise ProductNameAlreadyExistsException(name=name) from exc
            raise

    async def update(self, product: Product) -> None:
        name = product.name
        try:
            await self._session.flush()
        except IntegrityError as exc:
            pgcode = getattr(exc.orig, "pgcode", None)
            if pgcode == pg_excs.UniqueViolationError.sqlstate and product.UQ_NAME in str(exc.orig):
                raise ProductNameAlreadyExistsException(name=name) from exc
            raise

    async def get_by_id(self, product_id: UUID) -> Product | None:
        stmt = select(Product).where(
            Product.product_id == product_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(self, include_deactivated: bool) -> list[Product]:
        stmt = select(Product)
        if not include_deactivated:
            stmt = stmt.where(
                Product.is_active.is_(True),
            )
        stmt = stmt.order_by(desc(Product.created_at), desc(Product.product_id))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def search_by_fuzzy(self, name: str) -> Product | None:
        await self._session.execute(
            select(func.set_config(
                "pg_trgm.similarity_threshold",
                str(self._FUZZY_THRESHOLD),
                True,
            )),
        )

        similarity = func.similarity(Product.name, name)
        stmt = (
            select(Product)
            .where(
                Product.name.bool_op("%")(name),
                similarity >= self._FUZZY_THRESHOLD,
            )
            .order_by(
                similarity.desc(),
                desc(Product.created_at),
                desc(Product.product_id),
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
