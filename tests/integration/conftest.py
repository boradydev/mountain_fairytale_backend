from os import environ
from pathlib import Path

import pytest


@pytest.fixture
def config_dir() -> Path:
    return Path(environ["CONFIG_DIR"])
