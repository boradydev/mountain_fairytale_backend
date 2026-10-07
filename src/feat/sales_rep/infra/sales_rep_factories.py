from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.feat.sales_rep.app.usecases.check_duplicate import CheckSalesRepresentativeDuplicateUseCase
from src.feat.sales_rep.app.usecases.create import CreateSalesRepresentativeUseCase
from src.feat.sales_rep.app.usecases.get import GetSalesRepresentativeUseCase
from src.feat.sales_rep.app.usecases.get_all import GetSalesRepresentativesUseCase
from src.feat.sales_rep.app.usecases.update import UpdateSalesRepresentativeUseCase
from src.feat.sales_rep.infra.sales_rep_uow import SalesRepresentativesUOW


class SalesRepresentativesUseCaseFactory:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._session_factory = session_factory

    def get_sales_representative(self) -> GetSalesRepresentativeUseCase:
        return GetSalesRepresentativeUseCase(
            uow=self._create_uow(),
        )

    def get_sales_representatives(self) -> GetSalesRepresentativesUseCase:
        return GetSalesRepresentativesUseCase(
            uow=self._create_uow(),
        )

    def create_sales_representative(self) -> CreateSalesRepresentativeUseCase:
        return CreateSalesRepresentativeUseCase(
            uow=self._create_uow(),
        )

    def update_sales_representative(self) -> UpdateSalesRepresentativeUseCase:
        return UpdateSalesRepresentativeUseCase(
            uow=self._create_uow(),
        )

    def check_duplicate(self) -> CheckSalesRepresentativeDuplicateUseCase:
        return CheckSalesRepresentativeDuplicateUseCase(
            uow=self._create_uow(),
        )

    def _create_uow(self) -> SalesRepresentativesUOW:
        return SalesRepresentativesUOW(
            session_factory=self._session_factory,
        )

    @property
    def create_uow(self) -> SalesRepresentativesUOW:
        return self._create_uow()
