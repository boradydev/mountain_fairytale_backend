from uuid import UUID

from asyncpg import exceptions as pg_excs
from sqlalchemy import select, desc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.feat.employees.domain.abcs.employee_repo_abcs import IEmployeesRepository
from src.feat.employees.domain.employee_entities import Employee
from src.feat.employees.domain.employee_excs import EmployeeUsernameAlreadyExistsException


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
        username = employee.username
        try:
            await self._session.flush()
        except IntegrityError as exc:
            pgcode = getattr(exc.orig, "pgcode", None)
            if pgcode == pg_excs.UniqueViolationError.sqlstate and employee.UQ_USERNAME in str(exc.orig):
                raise EmployeeUsernameAlreadyExistsException(username=username) from exc

            raise

    async def update(
        self,
        employee: Employee,
    ) -> None:
        username = employee.username
        try:
            await self._session.flush()
        except IntegrityError as exc:
            pgcode = getattr(exc.orig, "pgcode", None)
            if pgcode == pg_excs.UniqueViolationError.sqlstate and employee.UQ_USERNAME in str(exc.orig):
                raise EmployeeUsernameAlreadyExistsException(username=username) from exc

            raise

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

    async def get_all(
        self,
        include_deactivated: bool,
    ) -> list[Employee]:
        stmt = select(Employee).order_by(
            desc(Employee.created_at),
        )

        if not include_deactivated:
            stmt = stmt.where(Employee.is_active.is_(True))

        result = await self._session.execute(stmt)

        return list(result.scalars().all())
