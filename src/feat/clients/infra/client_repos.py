import re
from datetime import datetime, time
from typing import Literal
from uuid import UUID

from asyncpg import exceptions as pg_excs
from sqlalchemy import bindparam, case, func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy.orm.attributes import set_committed_value

from src.feat.clients.domain.abcs.client_repo_abcs import IClientsRepository
from src.feat.clients.domain.client_entities import Client
from src.feat.clients.domain.client_excs import (
    ClientPhoneAlreadyExistsException,
    ClientRelatedEntityNotFoundException,
)
from src.feat.clients.domain.client_order_models import LastOrder, LastOrderItem


class ClientsRepository(IClientsRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, client: Client) -> None:
        self._session.add(client)
        await self._flush_with_constraint_handling(client)
        await self._session.refresh(client)
        await self._load_last_orders([client])

    async def update(self, client: Client) -> None:
        await self._flush_with_constraint_handling(client)
        await self._session.refresh(client)
        await self._load_last_orders([client])

    async def _load_last_orders(self, clients: list[Client]) -> None:
        if not clients:
            return
        # One query per page, including only points with actual order lines.
        stmt = text("""
            WITH sales AS (
                SELECT p.client_id, d.planned_date, d.document_type,
                       d.created_at, d.delivery_document_id,
                       i.product_id, i.product_name, i.quantity
                FROM points p
                JOIN delivery_documents d USING (delivery_document_id)
                JOIN delivery_document_items i USING (point_id)
                WHERE d.is_active AND p.client_id IN :client_ids
            ), latest AS (
                SELECT client_id, max(planned_date) AS planned_date
                FROM sales GROUP BY client_id
            )
            SELECT s.* FROM sales s JOIN latest USING (client_id, planned_date)
            ORDER BY s.created_at DESC, s.delivery_document_id DESC, s.product_id
        """).bindparams(bindparam("client_ids", expanding=True))
        rows = (await self._session.execute(stmt, {"client_ids": [c.client_id for c in clients]})).mappings()
        orders = {}
        for row in rows:
            order = orders.setdefault(row["client_id"], {"date": row["planned_date"], "types": set(), "items": {}})
            order["types"].add("delivery" if row["document_type"] == "delivery_route_sheet" else "pickup")
            items = order["items"]
            product_id = row["product_id"]
            if product_id not in items:
                # First occurrence uses the latest document's historical name.
                items[product_id] = LastOrderItem(product_id, row["product_name"], row["quantity"])
            else:
                old = items[product_id]
                items[product_id] = LastOrderItem(product_id, old.product_name, old.quantity + row["quantity"])
        for client in clients:
            order = orders.get(client.client_id)
            summary = None
            if order:
                types: list[Literal["delivery", "pickup"]] = [
                    kind for kind in ("delivery", "pickup") if kind in order["types"]
                ]
                summary = LastOrder(
                    date=order["date"],
                    fulfillment_types=types,
                    items=sorted(
                        order["items"].values(), key=lambda item: (item.product_name.casefold(), item.product_id)
                    ),
                )
            client.last_order = summary
            # Compatibility fields are projections too, not updates to the ORM entity.
            set_committed_value(
                client, "last_delivery_date", datetime.combine(summary.date, time.min) if summary else None
            )
            set_committed_value(
                client, "last_delivery_quantity", sum(item.quantity for item in summary.items) if summary else None
            )

    async def _flush_with_constraint_handling(self, client: Client) -> None:
        # Нужно переменные создать заранее, иначе после ошибка от asyncpg к атрибутам уже не обратится.
        phone = client.phone
        sales_representative_id = client.sales_representative_id
        default_payment_method_id = client.default_payment_method_id

        try:
            await self._session.flush()
        except IntegrityError as exc:
            # Получаем код ошибки (работает как для asyncpg, так и для большинства других драйверов)
            pgcode = getattr(exc.orig, "pgcode", None)
            err_msg = str(exc.orig)

            # 1. Проверка уникальности телефона
            if pgcode == pg_excs.UniqueViolationError.sqlstate and client.UQ_PHONE in err_msg:
                raise ClientPhoneAlreadyExistsException(
                    phone=phone,
                ) from exc

            # 2. Проверка внешнего ключа торгового представителя
            if pgcode == pg_excs.ForeignKeyViolationError.sqlstate and client.FK_SALES_REPRESENTATIVE in err_msg:
                if sales_representative_id is not None:
                    raise ClientRelatedEntityNotFoundException(
                        field="sales_representative_id",
                        entity_id=sales_representative_id,
                    ) from exc

            # 3. Проверка внешнего ключа метода оплаты
            if pgcode == pg_excs.ForeignKeyViolationError.sqlstate and client.FK_PAYMENT_METHOD in err_msg:
                if default_payment_method_id is not None:
                    raise ClientRelatedEntityNotFoundException(
                        field="default_payment_method_id",
                        entity_id=default_payment_method_id,
                    ) from exc

            raise

    async def get_by_id(self, client_id: UUID) -> Client | None:
        stmt = select(Client).where(Client.client_id == client_id)
        result = await self._session.execute(stmt)
        client = result.unique().scalar_one_or_none()
        await self._load_last_orders([client] if client else [])
        return client

    async def get_all(
        self,
        *,
        include_deactivated: bool,
        offset: int,
        limit: int,
        search: str | None = None,
    ) -> tuple[list[Client], int]:
        filters = []
        if not include_deactivated:
            filters.append(Client.is_active.is_(True))

        term = (search or "").strip()
        if term:
            matches = [
                Client.name.icontains(term, autoescape=True),
                Client.address.icontains(term, autoescape=True),
            ]
            digits = re.sub(r"[^0-9]", "", term)
            if digits:
                matches.append(func.regexp_replace(Client.phone, "[^0-9]", "", "g").contains(digits))
            filters.append(or_(*matches))

        count_stmt = select(func.count()).select_from(Client).where(*filters)
        total = int((await self._session.execute(count_stmt)).scalar_one())

        stmt = (
            select(Client)
            .where(*filters)
            .order_by(Client.created_at.desc(), Client.client_id.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        clients = list(result.unique().scalars().all())
        await self._load_last_orders(clients)
        return clients, total

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
            .options(
                joinedload(Client.sales_representative),
                joinedload(Client.default_payment_method),
            )
            .where(matching_fields >= 2)
            .order_by(
                total_similarity.desc(),
                Client.created_at.desc(),
                Client.client_id.desc(),
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        client = result.unique().scalar_one_or_none()
        await self._load_last_orders([client] if client else [])
        return client
