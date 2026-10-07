from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.feat.products.app.abcs.product_uow_abcs import IProductsUOW
from src.feat.products.domain.abcs.product_repo_abcs import IProductsRepository
from src.feat.products.infra.product_repos import ProductsRepository
from src.common.infra.db.postgres.common import IPostgresUOW
from src.common.infra.services.event_pud_service import EventPublisher


class ProductsUOW(IPostgresUOW, IProductsUOW):
    _products: IProductsRepository

    @property
    def products(self) -> IProductsRepository:
        return self._products

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._session_factory = session_factory

    async def __aenter__(self) -> Self:
        self._session = self._session_factory()
        self._event_publisher = EventPublisher(
            session=self._session,
        )

        self._products = ProductsRepository(
            session=self._session,
        )

        return self
