"""Report current VM disk/backup failures, without uptime checks or an event queue."""

import json
import os
import shutil
import subprocess
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from urllib.request import ProxyHandler, Request, build_opener

from scripts.deploy.install_support_vpn import environment


def disk_condition(free: int, total: int) -> str:
    percent = 100 * free / total
    return "critical" if percent < 10 else "warning" if percent < 20 else "ok"


def backup_condition(state: dict) -> str:
    if state.get("lastError"):
        return "backup_failed"
    if state.get("cleanupRequired"):
        return "cleanup_failed"
    return "ok"


def report(dsn: str, source: str, condition: str, environment_name: str) -> bool:
    parts = urlsplit(dsn)
    project = parts.path.strip("/")
    if parts.scheme not in {"http", "https"} or not parts.username or not project.isdigit():
        return False
    host = parts.netloc.rsplit("@", 1)[-1]
    target = urlunsplit((parts.scheme, host, f"/api/{project}/store/", "", ""))
    level = "info" if condition == "ok" else "warning" if condition == "warning" else "error"
    event = {
        "event_id": uuid.uuid4().hex, "timestamp": datetime.now(UTC).isoformat(),
        "platform": "other", "level": level,
        "message": f"{source}: {'recovered' if condition == 'ok' else condition}",
        "environment": environment_name, "release": "operations@1",
        "fingerprint": ["operations", environment_name, source],
        "tags": {"component": source, "condition": condition},
    }
    request = Request(target, data=json.dumps(event).encode(), headers={
        "Content-Type": "application/json", "X-Sentry-Auth": f"Sentry sentry_version=7,sentry_key={parts.username}",
    })
    try:
        with build_opener(ProxyHandler({})).open(request, timeout=3) as response:
            return response.status == 200
    except (OSError, ValueError):
        return False


def check(root: Path) -> None:
    values = environment(root)
    dsn = values.get("OPERATIONS_SENTRY_DSN", "")
    if not dsn:
        return
    state_path = root / ".deploy/operations-status.json"
    try:
        sent = json.loads(state_path.read_text())
    except (FileNotFoundError, ValueError):
        sent = {}
    if not isinstance(sent, dict):
        sent = {}
    usage = shutil.disk_usage("/")
    conditions = {"vm_disk": disk_condition(usage.free, usage.total)}
    try:
        deployment = json.loads((root / ".deploy/state.json").read_text())
        if "backupError" in deployment:
            conditions["predeploy_backup"] = "backup_failed" if deployment["backupError"] else "ok"
    except (FileNotFoundError, ValueError):
        pass
    for source, container in (
        ("api_backup", "mountain-fairytale-backup-1"),
        ("monitoring_backup", "mountain-fairytale-monitoring-backup-1"),
    ):
        try:
            result = subprocess.run(
                ["docker", "exec", container, "cat", "/state/status.json"],
                capture_output=True, text=True, timeout=15,
            )
            data = json.loads(result.stdout) if result.returncode == 0 else None
            if isinstance(data, dict):
                conditions[source] = backup_condition(data)
            else:
                print(f"Backup state unreadable, check skipped: {source}")
        except (ValueError, subprocess.TimeoutExpired):
            print(f"Backup state unreadable, check skipped: {source}")
    for source, condition in conditions.items():
        previous = sent.get(source, "ok")
        if previous == condition:
            continue
        if report(dsn, source, condition, values.get("SENTRY_ENVIRONMENT", "production")):
            sent[source] = condition
            print(f"Operations event accepted: {source} {condition}")
        else:
            print(f"Operations event delivery unavailable: {source}; retry current state at next check")
    descriptor, temporary = tempfile.mkstemp(prefix=".operations-", dir=state_path.parent)
    with os.fdopen(descriptor, "w") as stream:
        json.dump(sent, stream)
    os.replace(temporary, state_path)


if __name__ == "__main__":
    check(Path("/opt/mountain-fairytale"))
