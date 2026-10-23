from pathlib import Path

import pytest

from scripts.deploy.init_backup_env import save_credentials


def test_append_preserves_database_settings_without_trailing_newline(tmp_path: Path):
    path = tmp_path / ".env"
    original = "POSTGRES_PASSWORD='keep$exact#value'\nAPI_IMAGE=unchanged"
    path.write_text(original, encoding="utf-8")
    save_credentials(path, "access", "secret")
    assert path.read_text(encoding="utf-8").startswith(original + "\n")
    before = path.read_bytes()
    with pytest.raises(ValueError, match="already exist"):
        save_credentials(path, "replacement", "replacement")
    assert path.read_bytes() == before


@pytest.mark.parametrize("line", ["AWS_ACCESS_KEY_ID=old", " export AWS_SECRET_ACCESS_KEY = 'old'"])
def test_existing_keys_are_not_overwritten(tmp_path: Path, line: str):
    path = tmp_path / ".env"
    path.write_text(line, encoding="utf-8")
    with pytest.raises(ValueError, match="already exist"):
        save_credentials(path, "access", "secret")
    assert path.read_text(encoding="utf-8") == line


@pytest.mark.parametrize("value", ["", "key\nINJECTED=value", "key\rvalue", "key\0value"])
def test_invalid_keys_do_not_modify_env(tmp_path: Path, value: str):
    path = tmp_path / ".env"
    path.write_text("API_IMAGE=unchanged\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Keys must be nonempty single-line values"):
        save_credentials(path, "access", value)
    assert path.read_text(encoding="utf-8") == "API_IMAGE=unchanged\n"
