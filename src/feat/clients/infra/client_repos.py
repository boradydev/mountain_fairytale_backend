from uuid import UUID

from asyncpg import exceptions as pg_excs
from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.feat.clients.domain.abcs.client_repo_abcs import IClientsRepository
from src.feat.clients.domain.client_entities import Client
from src.feat.clients.domain.client_excs import (
    ClientPhoneAlreadyExistsException,
    ClientRelatedEntityNotFoundException,
)
from src.feat.pay_methods.domain.pay_method_entities import PaymentMethod
from src.feat.sales_rep.domain.sales_rep_entities import SalesRepresentative


class ClientsRepository(IClientsRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, client: Client) -> None:
        self._session.add(client)
        await self._flush_with_constraint_handling(client)

    async def update(self, client: Client) -> None:
        await self._flush_with_constraint_handling(client)

    async def _flush_with_constraint_handling(self, client: Client) -> None:
        try:
            await self._session.flush()
        except IntegrityError as exc:
            constraint_name = self._constraint_name(exc)
            sqlstate = self._sqlstate(exc)

            if (
                sqlstate == pg_excs.UniqueViolationError.sqlstate
                and constraint_name == Client.UQ_PHONE
            ):
                raise ClientPhoneAlreadyExistsException(
                    phone=client.phone,
                ) from exc

            if (
                sqlstate == pg_excs.ForeignKeyViolationError.sqlstate
                and constraint_name == Client.FK_SALES_REPRESENTATIVE
            ):
                entity_id = client.sales_representative_id
                if entity_id is not None:
                    raise ClientRelatedEntityNotFoundException(
                        field="sales_representative_id",
                        entity_id=entity_id,
                    ) from exc

            if (
                sqlstate == pg_excs.ForeignKeyViolationError.sqlstate
                and constraint_name == Client.FK_PAYMENT_METHOD
            ):
                entity_id = client.default_payment_method_id
                if entity_id is not None:
                    raise ClientRelatedEntityNotFoundException(
                        field="default_payment_method_id",
                        entity_id=entity_id,
                    ) from exc

            raise

    @staticmethod
    def _constraint_name(exc: IntegrityError) -> str | None:
        orig = exc.orig
        constraint_name = getattr(orig, "constraint_name", None)
        if constraint_name:
            return str(constraint_name)

        diagnostic = getattr(orig, "diag", None)
        constraint_name = getattr(diagnostic, "constraint_name", None)
        if constraint_name:
            return str(constraint_name)

        return None

    @staticmethod
    def _sqlstate(exc: IntegrityError) -> str | None:
        orig = exc.orig
        return getattr(orig, "sqlstate", getattr(orig, "pgcode", None))

    async def get_by_id(self, client_id: UUID) -> Client | None:
        stmt = (
            select(Client)
            .options(joinedload(Client.sales_representative))
            .where(Client.client_id == client_id)
        )
        result = await self._session.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def get_all(
        self,
        *,
        include_deactivated: bool,
        offset: int,
        limit: int,
    ) -> tuple[list[Client], int]:
        filters = []
        if not include_deactivated:
            filters.append(Client.is_active.is_(True))

        count_stmt = select(func.count()).select_from(Client).where(*filters)
        total = int((await self._session.execute(count_stmt)).scalar_one())

        stmt = (
            select(Client)
            .options(joinedload(Client.sales_representative))
            .where(*filters)
            .order_by(Client.created_at.desc(), Client.client_id.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.unique().scalars().all()), total

    async def search_duplicate(
        self,
        *,
        name: str,
        phone: str,
        address: str,
    ) -> Client | None:
        name_similarity = func.similarity(Client.name, name)
        phone_similarity = func.similarity(Client.phone, phone)
        address_similarity = func.similarity(Client.address, address)

        matching_fields = (
            case((name_similarity >= 0.35, 1), else_=0)
            + case((phone_similarity >= 0.50, 1), else_=0)
            + case((address_similarity >= 0.25, 1), else_=0)
        )
        total_similarity = name_similarity + phone_similarity + address_similarity

        stmt = (
            select(Client)
            .options(joinedload(Client.sales_representative))
            .where(matching_fields >= 2)
            .order_by(
                total_similarity.desc(),
                Client.created_at.desc(),
                Client.client_id.desc(),
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def sales_representative_exists(self, entity_id: UUID) -> bool:
        stmt = (
            select(SalesRepresentative.sales_representative_id)
            .where(SalesRepresentative.sales_representative_id == entity_id)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none() is not None

    async def payment_method_exists(self, entity_id: UUID) -> bool:
        stmt = (
            select(PaymentMethod.payment_method_id)
            .where(PaymentMethod.payment_method_id == entity_id)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none() is not None
