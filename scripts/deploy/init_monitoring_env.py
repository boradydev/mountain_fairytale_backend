"""Append monitoring defaults and generated secrets to an existing server dotenv."""

import argparse
import ipaddress
import json
import os
import re
import secrets
from pathlib import Path


def add_settings(path: Path, lan_host: str, vpn_host: str) -> None:
    lan = str(ipaddress.IPv4Address(lan_host))
    vpn = str(ipaddress.IPv4Address(vpn_host))
    content = path.read_text(encoding="utf-8")
    existing = set(re.findall(r"^\s*(?:export\s+)?([A-Z][A-Z0-9_]*)\s*=", content, re.M))
    values = {
        "GLITCHTIP_ENABLED": "true", "GLITCHTIP_PORT": "8080",
        "GLITCHTIP_PUBLIC_URL": f"http://{vpn}:8080",
        "GLITCHTIP_ALLOWED_HOSTS": f"{lan},{vpn},127.0.0.1,localhost,web",
        "GLITCHTIP_TRUSTED_ORIGINS": f"http://{lan}:8080,http://{vpn}:8080",
        "GLITCHTIP_POSTGRES_PASSWORD": secrets.token_hex(32),
        "GLITCHTIP_SECRET_KEY": secrets.token_hex(48),
        "GLITCHTIP_RETENTION_DAYS": "30", "GLITCHTIP_BACKUP_KEEP": "3",
        "GLITCHTIP_BACKUP_TIME": "17:15",
        "GLITCHTIP_BACKUP_S3_PREFIX": "mountain-fairytale/monitoring",
    }
    additions = {key: value for key, value in values.items() if key not in existing}
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        if content and not content.endswith("\n"):
            stream.write("\n")
        for key, value in additions.items():
            stream.write(f"{key}={json.dumps(value)}\n")
    if os.name != "nt":
        path.chmod(0o600)
    print(f"Added {len(additions)} monitoring variables; existing values preserved, secrets not printed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--lan-host", required=True)
    parser.add_argument("--vpn-host", default="10.77.50.11")
    args = parser.parse_args()
    if not args.path.is_file():
        parser.error("Existing server dotenv required")
    add_settings(args.path, args.lan_host, args.vpn_host)


if __name__ == "__main__":
    main()
