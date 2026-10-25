import logging
import re

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.common.api.excs_handlers import get_unknown_exception_handler
from src.common.api.request_ids import install_request_ids


def test_request_id_is_server_generated_and_present_on_errors():
    app = FastAPI()
    install_request_ids(app)
    app.add_exception_handler(Exception, get_unknown_exception_handler(logging.getLogger("request-test")))

    @app.get("/ok")
    async def ok():
        return {}

    @app.get("/error")
    async def error():
        raise RuntimeError("test-error")

    client = TestClient(app, raise_server_exceptions=False)
    first = client.get("/ok", headers={"X-Request-ID": "untrusted-input"})
    second = client.get("/error")
    assert re.fullmatch(r"[a-f0-9]{32}", first.headers["X-Request-ID"])
    assert re.fullmatch(r"[a-f0-9]{32}", second.headers["X-Request-ID"])
    assert first.headers["X-Request-ID"] != second.headers["X-Request-ID"]
    assert second.status_code == 500
