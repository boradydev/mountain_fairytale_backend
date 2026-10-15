import asyncio
from dataclasses import dataclass
from uuid import UUID, uuid4

from src.common.domain.events import BaseDomainEvent


@dataclass(frozen=True, slots=True)
class DashboardChangeState:
    server_id: UUID
    version: int
    clients_changed: bool
    delivery_days_changed: bool
    reload_required: bool


class DashboardChanges:
    """Уведомления одного процесса. Публикуются синхронно после COMMIT."""

    def __init__(self) -> None:
        self._server_id = uuid4()
        self._version = 0
        self._clients_version = 0
        self._days_version = 0
        self._changed = asyncio.Event()

    def publish(self, events: list[BaseDomainEvent]) -> None:
        subjects = {event.subject_type for event in events}
        days = bool(subjects & {"delivery_document", "delivery_point", "delivery_item"})
        clients = days or bool(subjects & {"client", "sales_representative", "payment_method"})
        if not clients and not days:
            return
        self._version += 1
        if clients:
            self._clients_version = self._version
        if days:
            self._days_version = self._version
        changed = self._changed
        self._changed = asyncio.Event()
        changed.set()

    async def wait(self, *, server_id: UUID | None, version: int | None, timeout: float) -> DashboardChangeState:
        reset = server_id != self._server_id or version is None or version > self._version
        if not reset and version == self._version and timeout > 0:
            changed = self._changed
            try:
                await asyncio.wait_for(changed.wait(), timeout=timeout)
            except TimeoutError:
                pass
        return DashboardChangeState(
            server_id=self._server_id,
            version=self._version,
            clients_changed=reset or self._clients_version > (version or 0),
            delivery_days_changed=reset or self._days_version > (version or 0),
            reload_required=reset,
        )
