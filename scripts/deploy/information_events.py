"""Positive lifecycle observations; no container-down alerts or historical replay."""

import re
import uuid
from collections.abc import Callable
from datetime import UTC, datetime


def timestamp(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC).isoformat()
    except ValueError:
        return None


def version(value: object) -> str:
    return value if isinstance(value, str) and re.fullmatch(r"\d+\.\d+\.\d+", value) else "unknown"


def commit(value: object) -> str:
    return value if isinstance(value, str) and re.fullmatch(r"[a-f0-9]{40}", value) else "unknown"


def observe(
    sent: dict, api: dict, deployment: dict, backups: dict[str, dict],
    emit: Callable[[dict], bool], environment_name: str,
) -> None:
    first_observation = not isinstance(sent.get("information"), dict)
    if first_observation:
        sent["information"] = dict.fromkeys(("api", "deployment", "backup:api_backup", "backup:monitoring_backup"), "")
    markers = sent["information"]
    candidates = []
    started = timestamp(api.get("startedAt"))
    container = api.get("id", "")
    if (
        api.get("health") == "healthy" and started and isinstance(container, str)
        and re.fullmatch(r"[a-f0-9]{64}", container)
    ):
        candidates.append(("api", f"{container}:{started}", "api_started", {
            "version": version(api.get("version")), "commitSha": commit(api.get("commitSha")),
            "startedAt": started, "containerId": container[:12],
        }))
    outcome = deployment.get("lastLifecycle") or {}
    name = outcome.get("event")
    deployment_id = outcome.get("deploymentId")
    if name in {"api_deployed", "api_deploy_failed"} and isinstance(deployment_id, int) and deployment_id > 0:
        details = {
            "deploymentId": deployment_id, "version": version(outcome.get("version")),
            "commitSha": commit(outcome.get("commitSha")),
            "previousVersion": version(outcome.get("previousVersion")),
            "previousCommitSha": commit(outcome.get("previousCommitSha")),
            "operation": "rollback" if outcome.get("operation") == "rollback" else "deploy",
        }
        if outcome.get("phase") in {"preflight", "backup", "migration", "starting", "checking", "committing"}:
            details["phase"] = outcome["phase"]
        occurred = timestamp(outcome.get("at"))
        if occurred:
            details["at"] = occurred
        candidates.append(("deployment", f"{deployment_id}:{name}", name, details))
    for source, state in backups.items():
        success = state.get("lastSuccess") or {}
        at = timestamp(success.get("at"))
        manifest = success.get("manifestKey", "")
        if not at or not isinstance(manifest, str):
            continue
        parts = manifest.split("/")
        if len(parts) < 2 or not re.fullmatch(r"\d{8}T\d{6}Z-[a-f0-9]{32}\.json", parts[-1]):
            continue
        candidates.append((f"backup:{source}", manifest, "backup_succeeded", {
            "source": source, "backupAt": at, "backupId": parts[-1],
            "category": parts[-2] if parts[-2] in {"daily", "manual", "predeploy"} else "unknown",
        }))
    for key, marker, name, details in candidates:
        if first_observation:
            # Existing installations establish a baseline, without replaying old starts/backups.
            markers[key] = marker
            continue
        if markers.get(key) == marker:
            continue
        event = {
            "event_id": uuid.uuid5(uuid.NAMESPACE_URL, f"{environment_name}:{key}:{marker}").hex,
            "timestamp": datetime.now(UTC).isoformat(), "platform": "other", "level": "info",
            "message": name, "environment": environment_name,
            "release": f"backend@{details['version']}" if "version" in details else "operations@1",
            "tags": {"event": name, "component": details.get("source", "backend")},
            "fingerprint": ["operations", environment_name, name, details.get("source", "backend")],
            "contexts": {"lifecycle": details},
        }
        if emit(event):
            markers[key] = marker
            print(f"Information event accepted: {name}")
