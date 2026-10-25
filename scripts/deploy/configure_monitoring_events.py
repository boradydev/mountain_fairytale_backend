"""Set SDK/public configuration from the private project metadata without printing DSNs."""

import json
import os
import re
from pathlib import Path

from scripts.deploy.install_support_vpn import environment


def main() -> None:
    if os.geteuid() != 0:
        raise SystemExit("Run as root")
    root = Path("/opt/mountain-fairytale")
    projects = {p["slug"]: p for p in json.loads((root / ".deploy/monitoring-projects.json").read_text())["projects"]}
    current = environment(root)
    port = current.get("GLITCHTIP_PORT", "8080")
    backend, flutter, operations = (projects[name] for name in ("backend", "flutter", "operations"))
    updates = {
        "SENTRY_DSN": f"http://{backend['publicKey']}@glitchtip:8000/{backend['id']}",
        "OPERATIONS_SENTRY_DSN": f"http://{operations['publicKey']}@127.0.0.1:{port}/{operations['id']}",
        "SENTRY_ENVIRONMENT": "production", "FLUTTER_MONITORING_ENABLED": "true",
        "FLUTTER_SENTRY_PUBLIC_KEY": flutter["publicKey"], "FLUTTER_SENTRY_PROJECT_ID": str(flutter["id"]),
    }
    updates = {key: value for key, value in updates.items() if not current.get(key)}
    allowed = current.get("GLITCHTIP_ALLOWED_HOSTS", "").split(",")
    if "glitchtip" not in allowed:
        updates["GLITCHTIP_ALLOWED_HOSTS"] = ",".join([*allowed, "glitchtip"])
    path = root / ".env"
    content = path.read_text()
    for key, value in updates.items():
        entry = f"{key}={json.dumps(value)}"
        if re.search(rf"^{key}=", content, re.M):
            content = re.sub(rf"^{key}=.*$", lambda _, replacement=entry: replacement, content, flags=re.M)
        else:
            content = content.rstrip("\n") + "\n" + entry + "\n"
    path.write_text(content)
    path.chmod(0o600)
    print(f"Configured {len(updates)} monitoring fields without displaying keys")


if __name__ == "__main__":
    main()
