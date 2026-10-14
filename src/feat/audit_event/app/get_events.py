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

    async def execute(
        self,
        *,
        search: str | None,
        cursor: str | None,
        limit: int,
        after: str | None = None,
        action: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> AuditPage:
        if cursor is not None and after is not None:
            raise InvalidAuditCursorException
        search = (search or "").strip().lower()
        for timestamp in (date_from, date_to):
            if timestamp is not None and timestamp.tzinfo is None:
                raise InvalidAuditCursorException
        date_from = date_from.astimezone(UTC) if date_from else None
        date_to = date_to.astimezone(UTC) if date_to else None
        if date_from and date_to and date_from >= date_to:
            raise InvalidAuditCursorException
        filter_text = (
            search
            if not any((action, date_from, date_to))
            else json.dumps(
                [search, action, date_from.isoformat() if date_from else None, date_to.isoformat() if date_to else None]
            )
        )
        fingerprint = hashlib.sha256(filter_text.encode()).hexdigest()
        before_at, before_id = self._decode_cursor(cursor, fingerprint) if cursor is not None else (None, None)
        after_at, after_id = self._decode_cursor(after, fingerprint, "newer") if after is not None else (None, None)
        async with self._uow as uow:
            rows = await uow.events.get_page(
                search=search,
                before_at=before_at,
                before_id=before_id,
                limit=limit + 1,
                after_at=after_at,
                after_id=after_id,
                action=action,
                date_from=date_from,
                date_to=date_to,
            )
        page = rows[:limit]
        next_cursor = None
        if len(rows) > limit:
            last = page[-1]
            next_cursor = self._encode_cursor(
                last.created_at, last.event_id, fingerprint, "newer" if after is not None else "older"
            )
        latest = page[-1] if after is not None and page else page[0] if page else None
        latest_cursor = (
            self._encode_cursor(latest.created_at, latest.event_id, fingerprint, "newer")
            if latest
            else (after or self._encode_cursor(datetime.min.replace(tzinfo=UTC), UUID(int=0), fingerprint, "newer"))
        )
        return AuditPage(events=[self._view(row) for row in page], next_cursor=next_cursor, latest_cursor=latest_cursor)

    @staticmethod
    def _encode_cursor(timestamp: datetime, event_id: UUID, fingerprint: str, direction: str) -> str:
        body = {"v": 1, "at": timestamp.isoformat(), "id": str(event_id), "filter": fingerprint, "direction": direction}
        return base64.urlsafe_b64encode(json.dumps(body).encode()).decode().rstrip("=")

    @staticmethod
    def _decode_cursor(cursor: str, fingerprint: str, direction: str = "older") -> tuple[datetime, UUID]:
        try:
            body = json.loads(base64.b64decode(cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True))
            if not isinstance(body, dict) or not isinstance(body.get("at"), str) or not isinstance(body.get("id"), str):
                raise ValueError("Invalid cursor shape")
            timestamp = datetime.fromisoformat(body["at"])
            if body["v"] != 1 or body["filter"] != fingerprint or timestamp.tzinfo is None:
                raise ValueError("Invalid cursor")
            if body.get("direction", "older") != direction:
                raise ValueError("Invalid cursor direction")
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
                "documentType": row.document_type,
            },
            data=public_values(payload.get("data", {})),
            changes=public_values(changes),
        )
