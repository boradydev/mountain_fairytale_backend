import sys
from io import TextIOWrapper
from logging import Logger
from unittest.mock import MagicMock

import pytest
from dotenv import load_dotenv


def pytest_configure():
    """
    Выполняется до запуска тестов.

    1. Инструкция stdout:
        Принудительно настраиваем stdout на работу с UTF-8.
        Решает проблему нечитаемых символов при выводе print (Windows, Linux, macOS).
        ``errors="replace"`` Заменит символ на ? которые не может закодировать.

    2. Инструкция load_dotenv:
        Загружает переменные из файла .env в окружение.
    """
    if isinstance(sys.stdout, TextIOWrapper):
        sys.stdout.reconfigure(
            encoding="utf-8",
            errors="replace",
        )

    load_dotenv()


@pytest.fixture
def mock_logger() -> MagicMock | Logger:
    return MagicMock(spec_set=Logger)
