"""Error reporting without request bodies, credentials or business data."""

import logging
import os
import re
import time
from pathlib import PurePath
from typing import Any

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from src.core.build_info import APP_COMMIT_SHA, APP_VERSION


_recent: dict[str, float] = {}


def private_event(event: dict[str, Any], _hint: dict[str, Any]) -> dict[str, Any] | None:
    # Allowlist instead of trying to enumerate all possible credential names.
    clean = {key: event[key] for key in (
        "event_id", "timestamp", "platform", "level", "release", "environment", "sdk",
    ) if key in event}
    exceptions = []
    for value in event.get("exception", {}).get("values", []):
        frames = []
        for frame in value.get("stacktrace", {}).get("frames", []):
            safe = {key: frame[key] for key in ("module", "function", "lineno", "in_app") if key in frame}
            safe["filename"] = PurePath(str(frame.get("filename") or "unknown").replace("\\", "/")).name
            frames.append(safe)
        exceptions.append({
            "type": value.get("type", "Exception"), "value": "Unexpected application error",
            "stacktrace": {"frames": frames},
        })
    if not exceptions:
        return None
    clean["exception"] = {"values": exceptions}
    clean["tags"] = {"component": "backend", "commit": APP_COMMIT_SHA}
    identifier = event.get("tags", {}).get("request_id", "")
    if isinstance(identifier, str) and re.fullmatch(r"[a-f0-9]{32}", identifier):
        clean["tags"]["request_id"] = identifier
    signature = repr(exceptions)
    now = time.monotonic()
    if now - _recent.get(signature, -60) < 60:
        return None
    if len(_recent) >= 128:
        _recent.clear()
    _recent[signature] = now
    return clean


def capture_error(exc: Exception, identifier: str) -> None:
    with sentry_sdk.new_scope() as scope:
        scope.set_tag("request_id", identifier)
        sentry_sdk.capture_exception(exc)


def initialize_monitoring() -> None:
    dsn = os.environ.get("SENTRY_DSN", "")
    if not dsn:
        return
    try:
        sentry_sdk.init(
            dsn=dsn, environment=os.environ.get("SENTRY_ENVIRONMENT", "production"),
            release=f"backend@{APP_VERSION}", send_default_pii=False,
            include_local_variables=False, max_request_body_size="never",
            traces_sample_rate=0, profiles_sample_rate=0, enable_logs=False,
            auto_session_tracking=False,
            send_client_reports=False,
            transport_queue_size=30, shutdown_timeout=1, before_send=private_event,
            integrations=[
                FastApiIntegration(), StarletteIntegration(),
                LoggingIntegration(level=None, event_level=None, sentry_logs_level=None),
            ],
        )
    except (ValueError, TypeError):
        logging.getLogger(__name__).warning("Monitoring disabled: invalid SDK configuration")
