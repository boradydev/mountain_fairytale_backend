from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.products.abcs.uow import IProductsUOW
from src.domain.products.abcs.products_repo_abcs import IProductsRepository
from src.infra.db.postgres.repos.products.products_repo import ProductsRepository
from src.infra.db.postgres.uow.common import IPostgresUOW
from src.infra.services.event_publisher.service import EventPublisher


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
