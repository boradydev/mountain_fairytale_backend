from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.common.cli import main as cli
from src.common.domain.const import SYSTEM_ACTOR_ID
from src.core.uuid7 import uuid7


@pytest.fixture
def admin_cli(monkeypatch):
    admin = SimpleNamespace(
        employee_id=uuid7(),
        username="Администратор",
        role="admin",
        is_active=True,
        password_hash="stored-secret-hash",
    )
    uow = AsyncMock()
    uow.__aenter__.return_value = uow
    uow.employees.get_admin.return_value = admin
    postgres = SimpleNamespace(session_factory=object(), dispose=AsyncMock())
    use_case = SimpleNamespace(execute=AsyncMock())
    monkeypatch.setattr(cli, "Postgres", lambda: postgres)
    monkeypatch.setattr(cli, "EmployeesUOW", lambda **_kwargs: uow)
    monkeypatch.setattr(cli, "PasswordService", Mock())
    monkeypatch.setattr(cli, "ChangeEmployeePasswordUseCase", Mock(return_value=use_case))
    monkeypatch.setattr(cli.getpass, "getpass", Mock(side_effect=AssertionError("Unexpected password prompt")))
    return SimpleNamespace(admin=admin, uow=uow, postgres=postgres, use_case=use_case)


@pytest.mark.parametrize("is_active", [True, False])
async def test_info_reads_actual_admin_without_password_prompt_or_writes(admin_cli, monkeypatch, capsys, is_active):
    admin_cli.admin.is_active = is_active
    monkeypatch.setenv("ADMIN_USERNAME", "outdated_env_login")

    await cli.show_admin_info()

    output = capsys.readouterr().out
    assert output == (f"Логин администратора: Администратор\nУчётная запись активна: {'да' if is_active else 'нет'}\n")
    assert admin_cli.admin.password_hash not in output
    admin_cli.uow.employees.get_admin.assert_awaited_once_with()
    admin_cli.uow.commit.assert_not_awaited()
    admin_cli.use_case.execute.assert_not_awaited()
    cli.getpass.getpass.assert_not_called()
    admin_cli.postgres.dispose.assert_awaited_once_with()


@pytest.mark.parametrize("command", [cli.show_admin_info, cli.change_admin_password])
async def test_missing_admin_does_not_create_account_and_closes_database(admin_cli, command):
    admin_cli.uow.employees.get_admin.return_value = None

    with pytest.raises(RuntimeError, match="Bootstrap-администратор не найден"):
        await command()

    cli.getpass.getpass.assert_not_called()
    admin_cli.uow.commit.assert_not_awaited()
    admin_cli.use_case.execute.assert_not_awaited()
    admin_cli.postgres.dispose.assert_awaited_once_with()


async def test_password_change_identifies_renamed_admin_before_hidden_input(admin_cli, monkeypatch, capsys):
    password = "new-cli-password"
    prompts = []

    def read_password(prompt):
        if not prompts:
            assert capsys.readouterr().out == "Смена пароля администратора: Администратор\n"
        prompts.append(prompt)
        return password

    monkeypatch.setattr(cli.getpass, "getpass", read_password)
    monkeypatch.setenv("ADMIN_USERNAME", "outdated_env_login")

    await cli.change_admin_password()

    assert prompts == ["Новый пароль: ", "Повторите новый пароль: "]
    admin_cli.use_case.execute.assert_awaited_once()
    dto = admin_cli.use_case.execute.call_args.args[0]
    assert dto.employee_id == admin_cli.admin.employee_id
    assert dto.actor_id == SYSTEM_ACTOR_ID
    assert dto.password == password
    output = capsys.readouterr().out
    assert "Пароль администратора 'Администратор' успешно изменён." in output
    assert password not in output
    assert admin_cli.admin.password_hash not in output
    admin_cli.postgres.dispose.assert_awaited_once_with()


async def test_password_mismatch_does_not_write_or_report_success(admin_cli, monkeypatch, capsys):
    monkeypatch.setattr(cli.getpass, "getpass", Mock(side_effect=["first-secret", "second-secret"]))

    with pytest.raises(RuntimeError, match="Пароли не совпадают"):
        await cli.change_admin_password()

    admin_cli.use_case.execute.assert_not_awaited()
    output = capsys.readouterr().out
    assert "успешно" not in output
    assert "first-secret" not in output
    assert "second-secret" not in output
    admin_cli.postgres.dispose.assert_awaited_once_with()


@pytest.mark.parametrize("command", ["info", "change-password"])
def test_main_dispatches_admin_subcommands(monkeypatch, command):
    info = AsyncMock()
    change_password = AsyncMock()
    monkeypatch.setattr(cli, "show_admin_info", info)
    monkeypatch.setattr(cli, "change_admin_password", change_password)
    monkeypatch.setattr("sys.argv", ["admin-cli", "admin", command])

    cli.main()

    if command == "info":
        info.assert_awaited_once_with()
        change_password.assert_not_awaited()
    else:
        change_password.assert_awaited_once_with()
        info.assert_not_awaited()
