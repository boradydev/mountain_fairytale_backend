from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.employees.abcs.repo import IEmployeesRepository
from src.domain.employees.entities import Employee
from src.infra.db.postgres.repos.employees.sql.registry import SQL


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
        params = {
            "employee_id": employee.employee_id,
            "username": employee.username,
            "password_hash": employee.password_hash,
            "role": employee.role,
            "is_active": employee.is_active,
            "created_at": employee.created_at,
        }

        await self._session.execute(
            SQL.ADD,
            params,
        )

    async def update(self, employee: Employee) -> None:
        changes = employee.get_changes()

        if not changes:
            return

        await self._session.execute(
            SQL.UPDATE(
                employee_id=employee.employee_id,
                changes=changes,
            ),
        )

        employee.clear_changes()

    async def get_by_id(
        self,
        employee_id: UUID,
    ) -> Employee | None:
        result = await self._session.execute(
            SQL.GET_BY_ID,
            {
                "employee_id": employee_id,
            },
        )

        row = result.mappings().one_or_none()

        if row is None:
            return None

        return Employee(
            _employee_id=row["employee_id"],
            _username=row["username"],
            _password_hash=row["password_hash"],
            _role=row["role"],
            _is_active=row["is_active"],
            _created_at=row["created_at"],
        )

    async def get_all(self) -> list[Employee]:
        result = await self._session.execute(
            SQL.GET_ALL,
        )

        rows = result.mappings().all()

        return [
            Employee(
                _employee_id=row["employee_id"],
                _username=row["username"],
                _password_hash=row["password_hash"],
                _role=row["role"],
                _is_active=row["is_active"],
                _created_at=row["created_at"],
            )
            for row in rows
        ]
