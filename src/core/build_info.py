import os
import tomllib

from src.core.paths import PROJECT_DIR


with (PROJECT_DIR / "pyproject.toml").open("rb") as project_file:
    APP_VERSION: str = tomllib.load(project_file)["tool"]["poetry"]["version"]

APP_COMMIT_SHA = os.environ.get("APP_COMMIT_SHA", "unknown")
