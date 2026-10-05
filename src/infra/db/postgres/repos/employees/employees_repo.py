from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.employees.abcs.employees_repo import IEmployeesRepository
from src.domain.employees.employee_entities import Employee


class EmployeesRepository(IEmployeesRepository):
    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._session = session

    async def add(
        self,
        employee: Employee,
    ) -> None:
        self._session.add(employee)

    async def update(
        self,
        employee: Employee,
    ) -> None:
        await self._session.flush()

    async def get_by_id(
        self,
        employee_id: UUID,
    ) -> Employee | None:
        stmt = select(Employee).where(
            Employee.employee_id == employee_id,
        )

        result = await self._session.execute(stmt)

        return result.scalar_one_or_none()

    async def get_by_username(
        self,
        username: str,
    ) -> Employee | None:
        stmt = select(Employee).where(
            Employee.username == username,
        )

        result = await self._session.execute(stmt)

        return result.scalar_one_or_none()

    async def get_all(self) -> list[Employee]:
        stmt = select(Employee).order_by(
            Employee.username,
        )

        result = await self._session.execute(stmt)

        return list(result.scalars().all())
