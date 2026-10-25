import logging

from src.core.request_id import RequestIdFilter


def logger_config() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s backend@%(backend_version)s "
        "env=%(environment)s request_id=%(request_id)s %(message)s",
    )
    for handler in logging.getLogger().handlers:
        handler.addFilter(RequestIdFilter())
