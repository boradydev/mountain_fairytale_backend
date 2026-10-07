from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.products.usecases.check_duplicate import CheckProductDuplicateUseCase
from src.app.products.usecases.create import CreateProductUseCase
from src.app.products.usecases.get import GetProductUseCase
from src.app.products.usecases.get_all import GetProductsUseCase
from src.app.products.usecases.update import UpdateProductUseCase
from src.infra.db.postgres.uow.products import ProductsUOW


class ProductsUseCaseFactory:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._session_factory = session_factory

    def create_product(self) -> CreateProductUseCase:
        return CreateProductUseCase(
            uow=self._create_uow(),
        )

    def get_product(self) -> GetProductUseCase:
        return GetProductUseCase(
            uow=self._create_uow(),
        )

    def get_products(self) -> GetProductsUseCase:
        return GetProductsUseCase(
            uow=self._create_uow(),
        )

    def update_product(self) -> UpdateProductUseCase:
        return UpdateProductUseCase(
            uow=self._create_uow(),
        )

    def check_duplicate(self) -> CheckProductDuplicateUseCase:
        return CheckProductDuplicateUseCase(
            uow=self._create_uow(),
        )

    def _create_uow(self) -> ProductsUOW:
        return ProductsUOW(
            session_factory=self._session_factory,
        )

    @property
    def create_uow(self) -> ProductsUOW:
        return self._create_uow()
