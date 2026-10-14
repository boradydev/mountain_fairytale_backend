import base64
import binascii
import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import inflection

from src.common.domain.event_record import AuditRecord
from src.feat.audit_event.app.abcs.audit_uow_abcs import IAuditUOW
from src.feat.audit_event.domain.audit_excs import InvalidAuditCursorException
from src.feat.audit_event.domain.audit_models import AuditEventView, AuditPage


def public_values(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            inflection.camelize(key, uppercase_first_letter=False): public_values(item)
            for key, item in value.items()
            if key not in {"password_hash", "password", "access_token", "refresh_token"}
        }
    if isinstance(value, list):
        return [public_values(item) for item in value]
    return value


class GetEventsUseCase:
    def __init__(self, uow: IAuditUOW) -> None:
        self._uow = uow

    async def execute(self, *, search: str | None, cursor: str | None, limit: int) -> AuditPage:
        search = (search or "").strip().lower()
        fingerprint = hashlib.sha256(search.encode()).hexdigest()
        before_at, before_id = self._decode_cursor(cursor, fingerprint) if cursor is not None else (None, None)
        async with self._uow as uow:
            rows = await uow.events.get_page(search=search, before_at=before_at, before_id=before_id, limit=limit + 1)
        page = rows[:limit]
        next_cursor = None
        if len(rows) > limit:
            last = page[-1]
            body = {"v": 1, "at": last.created_at.isoformat(), "id": str(last.event_id), "filter": fingerprint}
            next_cursor = base64.urlsafe_b64encode(json.dumps(body).encode()).decode().rstrip("=")
        return AuditPage(events=[self._view(row) for row in page], next_cursor=next_cursor)

    @staticmethod
    def _decode_cursor(cursor: str, fingerprint: str) -> tuple[datetime, UUID]:
        try:
            body = json.loads(base64.b64decode(cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True))
            if not isinstance(body, dict) or not isinstance(body.get("at"), str) or not isinstance(body.get("id"), str):
                raise ValueError("Invalid cursor shape")
            timestamp = datetime.fromisoformat(body["at"])
            if body["v"] != 1 or body["filter"] != fingerprint or timestamp.tzinfo is None:
                raise ValueError("Invalid cursor")
            return timestamp.astimezone(UTC), UUID(body["id"])
        except (ValueError, KeyError, TypeError, binascii.Error) as exc:
            raise InvalidAuditCursorException from exc

    @staticmethod
    def _view(row: AuditRecord) -> AuditEventView:
        payload = row.payload
        changes = {
            key: {"old_value": value.get("old"), "new_value": value.get("new")}
            for key, value in payload.get("changes", {}).items()
            if isinstance(value, dict) and "old" in value and "new" in value
        }
        return AuditEventView(
            event_id=row.event_id,
            operation_id=row.operation_id,
            event_type=row.event_type,
            created_at=row.created_at.astimezone(UTC),
            actor={"actorId": str(row.actor_id), "displayName": row.actor_name},
            action=row.action,
            subject={
                "type": payload.get("subject_type", "unknown"),
                "id": payload.get("subject_id", str(row.event_id)),
                "displayName": row.subject_name,
            },
            data=public_values(payload.get("data", {})),
            changes=public_values(changes),
        )
