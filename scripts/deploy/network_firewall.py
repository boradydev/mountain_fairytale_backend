"""Scoped IPv4 firewall for the published API and the support VPN interface."""

import ipaddress
import os
import re
import subprocess
from collections.abc import Mapping


def interface(value: str) -> str:
    if not re.fullmatch(r"[a-zA-Z0-9_.-]{1,15}", value):
        raise ValueError("Invalid network interface")
    return value


def rules(environment: Mapping[str, str]) -> str:
    lan = interface(environment["LAN_INTERFACE"])
    subnet = str(ipaddress.IPv4Network(environment["LAN_SUBNET"]))
    port = int(environment["API_PORT"])
    if not 1 <= port <= 65535:
        raise ValueError("Invalid API port")
    ports = [port]
    if environment.get("GLITCHTIP_ENABLED", "false").lower() == "true":
        monitoring_port = int(environment.get("GLITCHTIP_PORT", "8080"))
        if not 1 <= monitoring_port <= 65535 or monitoring_port == port:
            raise ValueError("Invalid or conflicting GlitchTip port")
        ports.append(monitoring_port)
    vpn = interface(environment.get("SUPPORT_VPN_INTERFACE", "support0"))
    enabled = environment.get("SUPPORT_VPN_ENABLED", "false").lower() == "true"
    admin = str(ipaddress.IPv4Address(environment["SUPPORT_VPN_ADMIN_IP"])) if enabled else None
    if vpn == lan:
        raise ValueError("LAN and VPN interfaces must be different")
    result = [
        "*filter", ":MF_FORWARD - [0:0]", ":MF_API - [0:0]", ":MF_VPN_INPUT - [0:0]",
        "-F MF_FORWARD", "-F MF_API", "-F MF_VPN_INPUT",
        "-A MF_FORWARD -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN",
        *[
            f"-A MF_FORWARD -p tcp -m conntrack --ctstate DNAT --ctdir ORIGINAL --ctorigdstport {item} -j MF_API"
            for item in ports
        ],
        f"-A MF_FORWARD -i {vpn} -j DROP",
        "-A MF_FORWARD -j RETURN",
        f"-A MF_API -i {lan} -s {subnet} -j ACCEPT",
    ]
    if admin:
        result += [f"-A MF_API -i {vpn} -s {admin}/32 -j ACCEPT"]
    result += ["-A MF_API -j DROP", "-A MF_VPN_INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT"]
    if admin:
        result += [
            f"-A MF_VPN_INPUT -s {admin}/32 -p tcp --dport 22 -j ACCEPT",
            f"-A MF_VPN_INPUT -s {admin}/32 -p icmp --icmp-type echo-request -j ACCEPT",
        ]
    result += ["-A MF_VPN_INPUT -j DROP", "COMMIT", ""]
    return "\n".join(result)


def main() -> None:
    if os.geteuid() != 0:
        raise SystemExit("Run as root")
    configuration = rules(os.environ)
    # One transaction replaces only our chains; Docker/UFW policies are preserved.
    subprocess.run(["iptables-restore", "--wait", "5", "--noflush"], input=configuration, text=True, check=True)
    vpn = interface(os.environ.get("SUPPORT_VPN_INTERFACE", "support0"))
    for chain, match, target in [("DOCKER-USER", [], "MF_FORWARD"), ("INPUT", ["-i", vpn], "MF_VPN_INPUT")]:
        rule = [*match, "-j", target]
        if subprocess.run(["iptables", "-w", "-C", chain, *rule], capture_output=True).returncode:
            subprocess.run(["iptables", "-w", "-I", chain, "1", *rule], check=True)


if __name__ == "__main__":
    main()
