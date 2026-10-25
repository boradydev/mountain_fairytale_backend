"""Prepare SSTP from the private server .env; never display configuration secrets."""

import argparse
import ipaddress
import json
import os
import re
import shutil
import socket
import ssl
import subprocess
from pathlib import Path

from scripts.deploy.network_firewall import interface


PROFILE = "mountain-fairytale-support"


def quote(value: str) -> str:
    if not value or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("VPN credentials must be nonempty single-line values")
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def configuration(values: dict[str, str]) -> tuple[str, str]:
    if values.get("SUPPORT_VPN_PROTOCOL", "sstp").lower() != "sstp":
        raise ValueError("This installer supports SSTP; WireGuard is a separate fallback procedure")
    host = values["SUPPORT_VPN_HOST"]
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9.-]{0,252}", host):
        raise ValueError("SUPPORT_VPN_HOST must be a DNS hostname without scheme, path or port")
    port = int(values.get("SUPPORT_VPN_PORT", "443"))
    if not 1 <= port <= 65535:
        raise ValueError("Invalid SSTP port")
    subnet = ipaddress.IPv4Network(values["SUPPORT_VPN_SUBNET"])
    local = ipaddress.IPv4Address(values["SUPPORT_VPN_EXPECTED_IP"])
    admin = ipaddress.IPv4Address(values["SUPPORT_VPN_ADMIN_IP"])
    if local == admin or local not in subnet or admin not in subnet:
        raise ValueError("Distinct VM/admin VPN addresses must belong to the support subnet")
    if subnet.overlaps(ipaddress.IPv4Network(values["LAN_SUBNET"])):
        raise ValueError("Support VPN must not overlap the client LAN")
    vpn = interface(values.get("SUPPORT_VPN_INTERFACE", "support0"))
    # sstpc 1.0.19 includes an explicit :443 in TLS SNI; Keenetic rejects it.
    endpoint = host if port == 443 else f"{host}:{port}"
    peer = "\n".join([
        f'pty "/usr/sbin/sstpc --ca-path /etc/ssl/certs --tls-ext --ipparam {PROFILE} '
        f'--nolaunchpppd {endpoint}"',
        "plugin sstp-pppd-plugin.so", f"sstp-sock /run/sstpc/sstpc-{PROFILE}",
        "user " + quote(values["SUPPORT_VPN_USERNAME"]), "password " + quote(values["SUPPORT_VPN_PASSWORD"]),
        f"remotename {PROFILE}", f"linkname {PROFILE}", f"ipparam {PROFILE}", f"ifname {vpn}",
        f"{local}:", "noauth", "nodefaultroute", "noipv6", "nopersist",
        "refuse-eap", "refuse-pap", "refuse-chap", "refuse-mschap",
        "nobsdcomp", "nodeflate", "lcp-echo-interval 10", "lcp-echo-failure 3", "hide-password", "",
    ])
    hook = "\n".join([
        "#!/bin/sh", "set -eu", f'[ "${{PPP_IPPARAM:-}}" = "{PROFILE}" ] || exit 0',
        f'[ "${{PPP_IFACE:-}}" = "{vpn}" ] || exit 1',
        f'[ "${{PPP_LOCAL:-}}" = "{local}" ] || exit 1',
        f"exec /usr/sbin/ip -4 route replace {subnet} dev {vpn} src {local}", "",
    ])
    return peer, hook


def environment(project: Path) -> dict[str, str]:
    result = subprocess.run(
        ["docker", "compose", "--project-directory", str(project), "config", "--environment"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode:
        raise ValueError("Cannot read server dotenv via Docker Compose; no values were printed")
    return dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)


def private_file(path: Path, content: str, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, mode)
    os.fchmod(descriptor, mode)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(content)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path("/opt/mountain-fairytale"))
    parser.add_argument("--check", action="store_true", help="Validate values and TLS without changing files")
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error("Run as root")
    try:
        values = environment(args.project)
        peer, hook = configuration(values)
        # Certificate chain AND hostname validation are mandatory.
        host = values["SUPPORT_VPN_HOST"]
        with socket.create_connection((host, int(values.get("SUPPORT_VPN_PORT", "443"))), timeout=10) as tcp:
            with ssl.create_default_context().wrap_socket(tcp, server_hostname=host):
                pass
        print("VPN configuration and TLS certificate verified; credentials were not printed")
        if args.check:
            return
        private_file(Path("/etc/ppp/peers") / PROFILE, peer)
        private_file(Path("/etc/ppp/ip-up.d") / PROFILE, hook, 0o700)
        # Kept root-readable; status checks contain only non-secret addresses.
        private_file(Path("/etc/ppp") / (PROFILE + ".json"), json.dumps({
            key: values[key] for key in ("SUPPORT_VPN_SUBNET", "SUPPORT_VPN_EXPECTED_IP", "SUPPORT_VPN_ADMIN_IP")
        }))
        shutil.copyfile(args.project / "deploy/mountain-fairytale-support-vpn.service",
                        Path("/etc/systemd/system/mountain-fairytale-support-vpn.service"))
        os.chmod("/etc/systemd/system/mountain-fairytale-support-vpn.service", 0o644)
        subprocess.run(["systemctl", "daemon-reload"], check=True)
        print("SSTP files prepared; apply firewall before enabling the VPN service")
    except (ValueError, KeyError, OSError, subprocess.SubprocessError):
        parser.exit(
            1, "SSTP preparation failed; verify configuration, connectivity and certificate. No secrets were printed.\n"
        )


if __name__ == "__main__":
    main()
