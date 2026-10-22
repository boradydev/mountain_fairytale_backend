"""Проверяет Ruff в изменённых Python-файлах, сохраняя старый lint-долг отдельно."""

import os
import subprocess
import sys
from pathlib import Path


def main() -> None:
    base = os.environ.get("BASE_SHA", "")
    if base and set(base) != {"0"}:
        command = ["git", "diff", "--name-only", "--diff-filter=ACMR", "-z", base, "HEAD"]
    else:
        command = ["git", "ls-files", "-z"]
    result = subprocess.run(command, check=True, capture_output=True)
    files = [
        name for name in result.stdout.decode("utf-8").split("\0") if name.endswith(".py") and Path(name).is_file()
    ]
    if files:
        subprocess.run([sys.executable, "-m", "ruff", "check", "--", *files], check=True)
    else:
        print("No changed Python files")


if __name__ == "__main__":
    main()
