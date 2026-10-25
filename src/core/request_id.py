import logging
import os
from contextvars import ContextVar

from src.core.build_info import APP_VERSION


request_id: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = request_id.get()
        record.backend_version = APP_VERSION
        record.environment = os.environ.get("SENTRY_ENVIRONMENT", "production")
        return True
