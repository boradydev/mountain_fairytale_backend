"""Publish immutable release records and select a production image on GitHub."""

import argparse
import base64
import json
import os
import re
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from scripts.deploy.release_manifest import (
    IMAGE,
    REPOSITORY,
    JsonObject,
    encode,
    schema_metadata,
    validate_release,
    validate_request,
)


BASE = f"https://api.github.com/repos/{REPOSITORY}"


def api(method: str, path: str, payload: JsonObject | None = None) -> JsonObject:
    request = Request(
        BASE + path,
        data=encode(payload) if payload is not None else None,
        method=method,
        headers={
            "Authorization": f"Bearer {os.environ['GH_TOKEN']}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.load(response)
    except HTTPError as exc:
        if exc.code == 404 and method == "GET":
            return {}
        raise RuntimeError(f"GitHub {method} failed: HTTP {exc.code}") from None


def read_file(path: str) -> tuple[JsonObject, str]:
    response = api("GET", f"/contents/{path}?ref=deployment")
    if not response:
        return {}, ""
    return json.loads(base64.b64decode(response["content"])), response["sha"]


def write_file(path: str, value: JsonObject, sha: str = "") -> None:
    payload = {
        "branch": "deployment",
        "message": f"deploy: update {path}",
        "content": base64.b64encode(encode(value)).decode(),
    }
    if sha:
        payload["sha"] = sha
    api("PUT", f"/contents/{path}", payload)


def output(**values: str) -> None:
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as stream:
        stream.write("".join(f"{name}={value}\n" for name, value in values.items()))


def prepare() -> None:
    commit = os.environ["GITHUB_SHA"]
    existing, _ = read_file(f"releases/{commit}.json")
    output(existing="true" if existing else "false", image=IMAGE)
    if existing:
        validate_release(existing)


def publish() -> None:
    commit = os.environ["GITHUB_SHA"]
    version = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["tool"]["poetry"]["version"]
    revision, migrations = schema_metadata(Path.cwd())
    release = validate_release({
        "image": IMAGE + "@" + os.environ["IMAGE_DIGEST"],
        "version": version,
        "commitSha": commit,
        "databaseRevision": revision,
        "migrations": migrations,
        "ciRunId": int(os.environ["GITHUB_RUN_ID"]),
    })
    if not api("GET", "/git/ref/heads/deployment"):
        api("POST", "/git/refs", {"ref": "refs/heads/deployment", "sha": commit})
    existing, _ = read_file(f"releases/{commit}.json")
    if existing:
        if existing != release:
            raise ValueError("A different release already exists for this commit")
    else:
        write_file(f"releases/{commit}.json", dict(release))
    print(f"Published {release['version']} from {commit}: {release['image']}")


def select() -> None:
    if os.environ["GITHUB_REF"] != "refs/heads/master":
        raise ValueError("Production selection must run from master")
    commit = os.environ["SELECTED_COMMIT"].strip()
    if not re.fullmatch(r"[a-f0-9]{40}", commit):
        raise ValueError("Provide the full 40-character commit SHA of a published build")
    value, _ = read_file(f"releases/{commit}.json")
    release = validate_release(value)
    run = api("GET", f"/actions/runs/{release['ciRunId']}")
    if not (
        run.get("status") == "completed"
        and run.get("conclusion") == "success"
        and run.get("head_sha") == commit == release["commitSha"]
        and run.get("head_branch") == "master"
        and run.get("event") == "push"
        and run.get("path") == ".github/workflows/backend-ci.yml"
        and run.get("repository", {}).get("full_name") == REPOSITORY
    ):
        raise ValueError("Selected build has no successful master Backend CI run")
    previous, sha = read_file("production.json")
    if previous:
        validate_request(previous)
    request = validate_request({
        **release,
        "deploymentId": previous.get("deploymentId", 0) + 1,
        "operation": os.environ["DEPLOY_OPERATION"],
        "compatibleRollback": os.environ.get("COMPATIBLE_ROLLBACK") == "true",
        "requestedAt": datetime.now(UTC).isoformat(),
        "requestedBy": os.environ["GITHUB_ACTOR"],
    })
    write_file("production.json", dict(request), sha)
    with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as summary:
        summary.write(
            f"### Deployment request #{request['deploymentId']}\n"
            f"Operation: {request['operation']}\n\nVersion: {release['version']}\n\n"
            f"Commit: `{commit}`\n\nImage: `{release['image']}`\n\n"
            "The request is saved. The VM applies it when online; this is not installation confirmation.\n"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "publish", "select"))
    args = parser.parse_args()
    if os.environ.get("GITHUB_REPOSITORY") != REPOSITORY:
        raise ValueError("Unexpected GitHub repository")
    {"prepare": prepare, "publish": publish, "select": select}[args.command]()


if __name__ == "__main__":
    main()
