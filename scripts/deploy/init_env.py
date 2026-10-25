"""Создаёт отдельное серверное окружение, не читая локальный .env проекта."""

import argparse
import ipaddress
import os
import secrets
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--bind-host", default="0.0.0.0")
    parser.add_argument("--lan-subnet", default="192.168.0.0/24")
    parser.add_argument("--lan-interface", default="eth0")
    parser.add_argument("--image", default="mountain-fairytale-api:1.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    ipaddress.IPv4Address(args.bind_host)
    ipaddress.IPv4Network(args.lan_subnet)
    if not 1 <= args.port <= 65535:
        parser.error("Port must be between 1 and 65535")
    values = {
        "API_IMAGE": args.image,
        "API_BIND_HOST": args.bind_host,
        "API_PORT": str(args.port),
        "LAN_SUBNET": args.lan_subnet,
        "LAN_INTERFACE": args.lan_interface,
        "SUPPORT_VPN_ENABLED": "false",
        "SUPPORT_VPN_PROTOCOL": "sstp",
        "SUPPORT_VPN_HOST": "",
        "SUPPORT_VPN_PORT": "443",
        "SUPPORT_VPN_USERNAME": "",
        "SUPPORT_VPN_PASSWORD": "",
        "SUPPORT_VPN_SUBNET": "10.77.50.0/24",
        "SUPPORT_VPN_EXPECTED_IP": "10.77.50.11",
        "SUPPORT_VPN_ADMIN_IP": "10.77.50.10",
        "SUPPORT_VPN_INTERFACE": "support0",
        "POSTGRES_DB": "mountain_fairytale",
        "POSTGRES_USER": "mountain_fairytale",
        "POSTGRES_PASSWORD": secrets.token_hex(32),
        "JWT_SECRET_KEY": secrets.token_hex(48),
        "ADMIN_USERNAME": "admin",
        "ADMIN_PASSWORD": secrets.token_urlsafe(24),
        "GEOAPIFY_API_KEY": "",
        "GEOAPIFY_TILE_CACHE_MAX_BYTES": "2147483648",
    }
    if any("\n" in value or "\r" in value for value in values.values()):
        parser.error("Environment values cannot contain newlines")
    fd = os.open(args.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as env_file:
        env_file.write("".join(f"{key}={value}\n" for key, value in values.items()))
    print(f"Created {args.path}; secrets were not printed. Existing files are never overwritten.")


if __name__ == "__main__":
    main()
