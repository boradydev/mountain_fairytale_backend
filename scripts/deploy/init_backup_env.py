"""Вводит S3-ключи в приватном терминале VM, не печатая и не перезаписывая их."""

import argparse
import getpass
import os
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    if args.path.exists():
        parser.error("File already exists; it was not modified")
    access = getpass.getpass("S3 Access Key (hidden): ")
    secret = getpass.getpass("S3 Secret Key (hidden): ")
    if any(not value or any(char in value for char in "\r\n\0") for value in (access, secret)):
        parser.error("Keys must be nonempty single-line values")
    descriptor = os.open(args.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(f"AWS_ACCESS_KEY_ID={access}\nAWS_SECRET_ACCESS_KEY={secret}\n")
    print("S3 credentials saved privately; values were not printed")


if __name__ == "__main__":
    main()
