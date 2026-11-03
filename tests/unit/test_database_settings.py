import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tests.integration import db_helpers


@pytest.mark.parametrize("name", ["mountain_fairytale_api_test", "mountain_fairytale_repo_test", "custom_test"])
def test_accepts_explicit_test_database_names(name: str) -> None:
    db_helpers.validate_test_database_name(name)


@pytest.mark.parametrize("name", ["mountain_fairytale_sales_live_20261101", "postgres", "", "db_test;DROP DATABASE db"])
def test_refuses_non_test_database_before_connecting(name: str, monkeypatch, tmp_path: Path) -> None:
    connect = MagicMock()
    monkeypatch.setattr(db_helpers, "create_engine", connect)
    with pytest.raises(ValueError, match="ending in _test"):
        db_helpers.bootstrap_test_database(name, tmp_path / "alembic.ini", tmp_path)
    connect.assert_not_called()


def test_bootstrap_selects_test_db_without_mutating_runtime_db(monkeypatch, tmp_path: Path) -> None:
    manual = "mountain_fairytale_sales_live_20261101"
    target = "mountain_fairytale_api_test"
    for key, value in {
        "POSTGRES_DB": manual,
        "POSTGRES_HOST": "127.0.0.1",
        "POSTGRES_PORT": "5432",
        "POSTGRES_USER": "test_user",
        "POSTGRES_PASSWORD": "test-only",
    }.items():
        monkeypatch.setenv(key, value)
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    connection.execute.return_value.scalar_one.return_value = target
    connection.execute.return_value.scalar.return_value = ["Тест"]
    create_engine = MagicMock(return_value=engine)
    migrate = MagicMock()
    monkeypatch.setattr(db_helpers, "create_engine", create_engine)
    monkeypatch.setattr(db_helpers.subprocess, "run", migrate)
    db_helpers.bootstrap_test_database(target, tmp_path / "alembic.ini", tmp_path)
    assert os.environ["POSTGRES_DB"] == manual
    assert create_engine.call_args.kwargs["url"].endswith("/" + target)
    assert migrate.call_args.kwargs["env"]["POSTGRES_DB"] == target
    engine.dispose.assert_called_once_with()


def test_bootstrap_refuses_unexpected_connection_before_schema_changes(monkeypatch, tmp_path: Path) -> None:
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    connection.execute.return_value.scalar_one.return_value = "mountain_fairytale_sales_live_20261101"
    monkeypatch.setattr(db_helpers, "create_engine", MagicMock(return_value=engine))
    with pytest.raises(RuntimeError, match="schema recreation refused"):
        db_helpers.bootstrap_test_database("mountain_fairytale_api_test", tmp_path / "alembic.ini", tmp_path)
    connection.execute.assert_called_once()
    assert str(connection.execute.call_args.args[0]) == "SELECT current_database()"
    engine.dispose.assert_called_once_with()
