"""Добавляет S3-ключи в общий .env, не печатая и не заменяя существующие ключи."""

import argparse
import getpass
import json
import os
from pathlib import Path
import re


KEYS = ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY")


def save_credentials(path: Path, access: str, secret: str) -> None:
    values = (access, secret)
    if any(not value or any(char in value for char in "\r\n\0") for value in values):
        raise ValueError("Keys must be nonempty single-line values")
    # Quote for Compose dotenv, escaping interpolation as well as special characters.
    additions = "".join(
        key + "=" + json.dumps(value, ensure_ascii=False).replace("$", "$$") + "\n"
        for key, value in zip(KEYS, values)
    )
    with path.open("r+", encoding="utf-8", newline="") as stream:
        original = stream.read()
        if any(re.search(r"^\s*(?:export\s+)?" + key + r"\s*=", original, re.MULTILINE) for key in KEYS):
            raise ValueError("S3 keys already exist; file was not modified")
        os.chmod(path, 0o600)
        stream.seek(0, os.SEEK_END)
        stream.write(("\n" if original and not original.endswith("\n") else "") + additions)
        stream.flush()
        os.fsync(stream.fileno())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Existing server .env")
    parser.add_argument("--from-legacy", type=Path, help="Import raw keys from an old backup.env without displaying them")
    args = parser.parse_args()
    if not args.path.is_file():
        parser.error("Create the server .env with init_env.py first")
    if args.from_legacy:
        values = {}
        for line in args.from_legacy.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator and key in KEYS:
                if key in values:
                    parser.error("Duplicate S3 key in legacy file; nothing was modified")
                values[key] = value
            elif line.strip() and not line.lstrip().startswith("#"):
                parser.error("Legacy file has extra settings; migrate those explicitly before continuing")
        access, secret = (values.get(key, "") for key in KEYS)
    else:
        access = getpass.getpass("S3 Access Key (hidden): ")
        secret = getpass.getpass("S3 Secret Key (hidden): ")
    try:
        save_credentials(args.path, access, secret)
    except ValueError as error:
        parser.error(str(error))
    print("S3 credentials saved privately; values were not printed")


if __name__ == "__main__":
    main()
