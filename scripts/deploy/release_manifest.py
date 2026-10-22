"""Validate release metadata shared by CI and the local deployment service."""

import ast
import hashlib
import json
import re
from pathlib import Path
from typing import Any, TypedDict


REPOSITORY = "boradydev/mountain_fairytale_backend"
IMAGE = f"ghcr.io/{REPOSITORY}"
# GitHub responses and persisted JSON have heterogeneous values; validate release fields at this boundary.
JsonObject = dict[str, Any]


class Release(TypedDict):
    image: str
    version: str
    commitSha: str
    databaseRevision: str
    migrations: dict[str, str]
    ciRunId: int


class Request(Release):
    deploymentId: int
    operation: str
    compatibleRollback: bool
    requestedAt: str
    requestedBy: str


def validate_release(value: object) -> Release:
    if not isinstance(value, dict):
        raise ValueError("Release must be a JSON object")
    patterns = {
        "image": re.escape(IMAGE) + r"@sha256:[a-f0-9]{64}",
        "version": r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)",
        "commitSha": r"[a-f0-9]{40}",
        "databaseRevision": r"[a-zA-Z0-9_]+",
    }
    for field, pattern in patterns.items():
        if not isinstance(value.get(field), str) or not re.fullmatch(pattern, value[field]):
            raise ValueError(f"Invalid release field: {field}")
    migrations = value.get("migrations")
    if not isinstance(migrations, dict) or value["databaseRevision"] not in migrations:
        raise ValueError("Missing migration checksums")
    for revision, checksum in migrations.items():
        if (
            not isinstance(revision, str)
            or not isinstance(checksum, str)
            or not re.fullmatch(r"[a-zA-Z0-9_]+", revision)
            or not re.fullmatch(r"[a-f0-9]{64}", checksum)
        ):
            raise ValueError("Invalid migration checksum")
    if type(value.get("ciRunId")) is not int or value["ciRunId"] < 1:
        raise ValueError("Invalid CI run ID")
    return Release(**{key: value[key] for key in Release.__required_keys__})


def validate_request(value: object) -> Request:
    release = validate_release(value)
    assert isinstance(value, dict)
    if type(value.get("deploymentId")) is not int or value["deploymentId"] < 1:
        raise ValueError("Invalid deployment ID")
    if value.get("operation") not in ("deploy", "rollback"):
        raise ValueError("Invalid deployment operation")
    if type(value.get("compatibleRollback")) is not bool:
        raise ValueError("Missing rollback confirmation")
    if value["operation"] == "rollback" and not value["compatibleRollback"]:
        raise ValueError("Rollback requires explicit compatibility confirmation")
    return Request(
        **release,
        deploymentId=value["deploymentId"],
        operation=value["operation"],
        compatibleRollback=value["compatibleRollback"],
        requestedAt=str(value.get("requestedAt", "")),
        requestedBy=str(value.get("requestedBy", "")),
    )


def schema_metadata(root: Path) -> tuple[str, dict[str, str]]:
    versions = root / "src/common/infra/db/postgres/alembic/migrations/versions"
    revisions: dict[str, str] = {}
    parents: set[str] = set()
    for migration in sorted(versions.glob("*/migration.py")):
        attributes: JsonObject = {}
        for node in ast.parse(migration.read_text(encoding="utf-8")).body:
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if node.target.id in ("revision", "down_revision") and node.value is not None:
                    attributes[node.target.id] = ast.literal_eval(node.value)
            elif isinstance(node, ast.Assign):
                for variable in node.targets:
                    if isinstance(variable, ast.Name) and variable.id in ("revision", "down_revision"):
                        attributes[variable.id] = ast.literal_eval(node.value)
        revision = attributes["revision"]
        parent = attributes["down_revision"]
        if parent:
            parents.update([parent] if isinstance(parent, str) else parent)
        digest = hashlib.sha256()
        for file in sorted(migration.parent.iterdir()):
            if file.suffix in (".py", ".sql"):
                digest.update(file.name.encode() + b"\0" + file.read_bytes().replace(b"\r\n", b"\n") + b"\0")
        if revision in revisions:
            raise ValueError("Duplicate migration revision")
        revisions[revision] = digest.hexdigest()
    if not parents.issubset(revisions):
        raise ValueError("Unknown migration parent")
    heads = set(revisions) - parents
    if len(heads) != 1:
        raise ValueError("Expected exactly one migration head")
    return heads.pop(), revisions


def encode(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n").encode()
