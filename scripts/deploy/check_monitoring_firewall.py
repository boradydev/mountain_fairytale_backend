"""Refuse publishing GlitchTip unless its Docker firewall rule is installed."""

import subprocess


def main() -> None:
    result = subprocess.run(
        ["docker", "compose", "--project-directory", "/opt/mountain-fairytale-monitoring",
         "--env-file", "/opt/mountain-fairytale/.env", "config", "--environment"],
        capture_output=True, text=True,
    )
    if result.returncode:
        raise SystemExit("Cannot validate monitoring environment; no values printed")
    values = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    if values.get("GLITCHTIP_ENABLED", "false").lower() != "true":
        raise SystemExit("Set GLITCHTIP_ENABLED=true and reload the firewall before starting monitoring")
    port = int(values.get("GLITCHTIP_PORT", "8080"))
    if not 1 <= port <= 65535:
        raise SystemExit("Invalid GlitchTip port")
    rules = [
        ["DOCKER-USER", "-j", "MF_FORWARD"],
        ["MF_FORWARD", "-p", "tcp", "-m", "conntrack", "--ctstate", "DNAT", "--ctdir", "ORIGINAL",
         "--ctorigdstport", str(port), "-j", "MF_API"],
    ]
    for rule in rules:
        if subprocess.run(["iptables", "-w", "-C", *rule], capture_output=True).returncode:
            raise SystemExit("Monitoring firewall missing; reload mountain-fairytale-firewall.service first")


if __name__ == "__main__":
    main()
