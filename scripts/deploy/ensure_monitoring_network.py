"""Create the shared transport network independently of either Compose lifecycle."""

import subprocess


def main() -> None:
    name = "mountain-fairytale-observability"
    if subprocess.run(["docker", "network", "inspect", name], capture_output=True).returncode:
        result = subprocess.run(["docker", "network", "create", name], capture_output=True)
        if result.returncode and subprocess.run(["docker", "network", "inspect", name], capture_output=True).returncode:
            raise SystemExit("Cannot create the monitoring transport network")


if __name__ == "__main__":
    main()
