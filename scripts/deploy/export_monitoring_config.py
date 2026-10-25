"""Export a private monitoring recovery bundle; copy it off the client PC."""

import argparse
import json
import os
import subprocess
import tarfile
import tempfile
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--project", type=Path, default=Path("/opt/mountain-fairytale"))
    parser.add_argument("--monitoring", type=Path, default=Path("/opt/mountain-fairytale-monitoring"))
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error("Run as root")
    # Exclusive creation prevents overwriting an earlier recovery bundle.
    descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as output, tempfile.TemporaryDirectory() as temporary:
            uploads = Path(temporary) / "uploads.tar"
            with uploads.open("wb") as stream:
                subprocess.run(
                    ["docker", "cp", "mountain-fairytale-monitoring-web-1:/code/uploads/.", "-"],
                    stdout=stream, stderr=subprocess.PIPE, check=True,
                )
            metadata = subprocess.run(
                ["docker", "inspect", "-f", "{{.Image}}", "mountain-fairytale-monitoring-web-1"],
                capture_output=True, text=True, check=True,
            ).stdout.strip()
            info = Path(temporary) / "recovery.json"
            info.write_text(json.dumps({"webImageId": metadata, "database": "glitchtip"}), encoding="utf-8")
            with tarfile.open(fileobj=output, mode="w:gz") as archive:
                archive.add(args.project / ".env", arcname="server.env")
                archive.add(args.monitoring / "compose.yaml", arcname="monitoring/compose.yaml")
                archive.add(uploads, arcname="uploads.tar")
                archive.add(info, arcname="recovery.json")
                for name in (
                    "init_monitoring_env.py", "setup_monitoring.py", "check_monitoring_firewall.py",
                    "export_monitoring_config.py", "network_firewall.py", "lan_firewall.sh",
                ):
                    archive.add(args.project / "scripts/deploy" / name, arcname="scripts/deploy/" + name)
                for name in ("mountain-fairytale-monitoring.service", "mountain-fairytale-firewall.service"):
                    archive.add(args.project / "deploy" / name, arcname="deploy/" + name)
                for name in ("monitoring-projects.json",):
                    path = args.project / ".deploy" / name
                    if path.is_file():
                        archive.add(path, arcname=name)
    except (OSError, subprocess.SubprocessError, tarfile.TarError):
        # Keep a failed output for diagnosis; do not mistake it for a verified bundle.
        raise SystemExit("Recovery export failed; no secrets printed. Do not use the incomplete output.") from None
    print(f"Private recovery bundle created: {args.output}; includes server secrets, not a database dump")
    print("Copy it to protected storage outside the client PC; pair with a verified S3 database backup")


if __name__ == "__main__":
    main()
