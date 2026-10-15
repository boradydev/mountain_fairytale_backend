from abc import ABC, abstractmethod
from datetime import date
from uuid import UUID

from src.feat.clients.domain.client_entities import Client
from src.feat.commissions.domain.commission_models import EmployeeAccrual, PointAccrual
from src.feat.employees.domain.employee_entities import Employee
from src.feat.sales_rep.domain.sales_rep_entities import SalesRepresentative


class ICommissionsRepository(ABC):
    @abstractmethod
    async def begin_report(self) -> None: ...

    @abstractmethod
    async def point_accruals(self, start: date, end: date) -> list[PointAccrual]: ...

    @abstractmethod
    async def employee_accruals(self, start: date, end: date) -> list[EmployeeAccrual]: ...

    @abstractmethod
    async def representatives(self) -> list[SalesRepresentative]: ...

    @abstractmethod
    async def employees(self) -> list[Employee]: ...

    @abstractmethod
    async def clients(self) -> list[Client]: ...

    @abstractmethod
    async def lock_representatives(self, ids: list[UUID]) -> list[SalesRepresentative]: ...

    @abstractmethod
    async def assigned_clients(self, representative_id: UUID) -> list[Client]: ...
