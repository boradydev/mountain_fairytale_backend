"""Apply a production image request using local Compose, backups and migrations."""

import argparse
import json
import logging
import os
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request as HTTPRequest, urlopen

from scripts.deploy.release_manifest import REPOSITORY, JsonObject, Release, Request, encode, validate_request


logger = logging.getLogger("deploy")
REQUEST_URL = f"https://raw.githubusercontent.com/{REPOSITORY}/deployment/production.json"
ACTIVE_PHASES = {"backup", "migration", "starting", "checking", "committing"}


class DeploymentError(Exception):
    pass


def save_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(".tmp")
    with temporary.open("wb") as stream:
        stream.write(encode(value))
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)
    if hasattr(os, "O_DIRECTORY"):
        descriptor = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def read_json(path: Path) -> JsonObject:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def fetch_request() -> Request | None:
    request = HTTPRequest(REQUEST_URL + f"?check={int(time.time())}", headers={"Cache-Control": "no-cache"})
    try:
        with urlopen(request, timeout=20) as response:
            body = response.read(65537)
    except HTTPError as exc:
        if exc.code == 404:
            return None
        raise DeploymentError(f"Cannot fetch production request: HTTP {exc.code}") from None
    except (URLError, TimeoutError, OSError):
        raise DeploymentError("Cannot fetch production request; current application is unchanged") from None
    if len(body) > 65536:
        raise DeploymentError("Production request is too large")
    return validate_request(json.loads(body))


class Runtime:
    def __init__(self, project: Path) -> None:
        self.project = project

    def command(self, args: list[str], *, image: str = "", timeout: int = 2400) -> str:
        environment = os.environ.copy()
        if image:
            environment["API_IMAGE"] = image
        result = subprocess.run(
            args, cwd=self.project, env=environment, text=True, capture_output=True, timeout=timeout,
        )
        if result.returncode:
            # Output can contain database URLs or application data. Keep it off GitHub and the journal.
            raise DeploymentError(f"Command failed (exit {result.returncode}): {' '.join(args[:3])}")
        return result.stdout.strip()

    def compose(self, *args: str, image: str = "", timeout: int = 2400) -> str:
        return self.command(
            ["docker", "compose", "-f", "compose.yaml", "-f", "compose.backup.yaml", *args],
            image=image, timeout=timeout,
        )

    def current_image(self) -> str:
        container = self.compose("ps", "-aq", "api")
        if not container:
            raise DeploymentError("API container not found; initialize the application first")
        return self.command(["docker", "inspect", "--format", "{{.Image}}", container])

    def inspect_release(self, release: Release) -> None:
        labels = json.loads(self.command([
            "docker", "image", "inspect", "--format", "{{json .Config.Labels}}", release["image"],
        ]))
        if labels.get("org.opencontainers.image.revision") != release["commitSha"]:
            raise DeploymentError("Image revision does not match the selected release")
        if labels.get("org.opencontainers.image.version") != release["version"]:
            raise DeploymentError("Image version does not match the selected release")
        revision, migrations = self.schema(release["image"])
        if revision != release["databaseRevision"] or migrations != release["migrations"]:
            raise DeploymentError("Image migrations do not match the selected release")

    def schema(self, image: str) -> tuple[str, dict[str, str]]:
        helper = Path(__file__).with_name("release_manifest.py").resolve()
        command = (
            "import sys,json; from pathlib import Path; sys.path.insert(0,'/tmp'); "
            "from release_manifest import schema_metadata; print(json.dumps(schema_metadata(Path('/app'))))"
        )
        result = self.command([
            "docker", "run", "--rm", "--network", "none", "--entrypoint", "python", "--mount",
            f"type=bind,src={helper},dst=/tmp/release_manifest.py,readonly", image, "-c", command,
        ])
        revision, migrations = json.loads(result)
        return revision, migrations

    def database_revision(self) -> str:
        query = (
            'exec psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -X -At -v ON_ERROR_STOP=1 '
            '-c "SELECT version_num FROM alembic_version"'
        )
        return self.compose("exec", "-T", "postgres", "sh", "-c", query, timeout=30)

    def ready(self, image: str) -> JsonObject:
        script = (
            "import json,urllib.request; "
            "print(json.dumps(json.load(urllib.request.urlopen('http://127.0.0.1:8000/health/ready',timeout=5))['data']))"
        )
        return json.loads(self.compose("exec", "-T", "api", "python", "-c", script, image=image, timeout=15))

    def start(self, image: str) -> None:
        self.compose("up", "-d", "--no-deps", "--wait", "--wait-timeout", "120", "api", image=image, timeout=150)

    def persist_image(self, image: str) -> None:
        path = self.project / ".env"
        lines = path.read_text(encoding="utf-8").splitlines()
        lines = [line for line in lines if not line.startswith("API_IMAGE=")]
        lines.append("API_IMAGE=" + image)
        temporary = self.project / ".env.deploy-tmp"
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write("\n".join(lines) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


class Deployer:
    def __init__(self, project: Path, runtime: Runtime | None = None) -> None:
        self.directory = project / ".deploy"
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.state_path = self.directory / "state.json"
        self.maintenance = self.directory / "maintenance"
        self.runtime = runtime or Runtime(project)

    def store(self, state: JsonObject) -> None:
        state["updatedAt"] = datetime.now(UTC).isoformat()
        save_json(self.state_path, state)

    def phase(self, state: JsonObject, phase: str) -> None:
        state["phase"] = phase
        self.store(state)
        logger.info("Deployment #%s: %s", state["lastAttemptedId"], phase)

    def check_compatibility(self, request: Request, state: JsonObject, current_image: str) -> None:
        revision, migrations = self.runtime.schema(current_image)
        if revision != self.runtime.database_revision():
            raise DeploymentError("Current image and database revisions differ; manual recovery is required")
        target = request["migrations"]
        if request["operation"] == "rollback":
            known = [state.get("current"), *state.get("history", [])]
            if not any(item and item["image"] == request["image"] for item in known):
                raise DeploymentError("Rollback target has never been successfully deployed on this VM")
            if target != migrations or request["databaseRevision"] != revision:
                raise DeploymentError("Rollback changes the database schema; use a separate recovery procedure")
        elif any(target.get(key) != checksum for key, checksum in migrations.items()):
            raise DeploymentError("Applied migrations were changed or removed; automatic deployment is blocked")
        elif state.get("current") and request["image"] != state["current"]["image"]:
            if any(item["image"] == request["image"] for item in state.get("history", [])):
                raise DeploymentError("Select operation=rollback for a previously deployed image")
            old_version = tuple(map(int, state["current"]["version"].split(".")))
            new_version = tuple(map(int, request["version"].split(".")))
            if new_version < old_version:
                raise DeploymentError("A lower application version requires operation=rollback")

    def apply(self, request: Request, *, recover: bool = False) -> JsonObject:
        import fcntl

        with (self.directory / "deploy.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise DeploymentError("Another deployment is running") from None
            return self.apply_locked(request, recover=recover)

    def apply_locked(self, request: Request, *, recover: bool = False) -> JsonObject:
        state = read_json(self.state_path)
        if state.get("phase") in ACTIVE_PHASES:
            state["phase"] = "interrupted"
            state["lastError"] = "Deployment was interrupted; inspect the database and recover manually"
            self.store(state)
        if request["deploymentId"] <= state.get("lastAttemptedId", 0):
            return state
        if (self.maintenance.exists() or state.get("phase") in ("interrupted", "failed-migration")) and not recover:
            raise DeploymentError("Maintenance state requires operator review and --recover")
        state.update(lastAttemptedId=request["deploymentId"], request=dict(request))
        self.phase(state, "preflight")
        current_image = ""
        stopped = migration_started = starting = False
        try:
            self.runtime.compose("config", "--quiet", image=request["image"])
            self.runtime.command(["docker", "pull", request["image"]])
            self.runtime.compose("pull", "backup", image=request["image"])
            self.runtime.inspect_release(request)
            current_image = self.runtime.current_image()
            self.check_compatibility(request, state, current_image)
            if state.get("current", {}).get("image") == request["image"]:
                ready = self.runtime.ready(request["image"])
                if (
                    ready.get("commitSha") != request["commitSha"]
                    or ready.get("version") != request["version"]
                    or ready.get("status") != "ready"
                ):
                    raise DeploymentError("Current API does not match the selected image")
                state["phase"] = "succeeded"
                state.pop("lastError", None)
                self.store(state)
                return state
            state["previous"] = state.get("current")
            state["previousLocalImage"] = current_image
            self.maintenance.touch(mode=0o600)
            self.phase(state, "backup")
            self.runtime.compose("stop", "api")
            stopped = True
            self.runtime.compose("run", "--rm", "--no-deps", "backup", "run", "--category", "predeploy")
            if request["operation"] != "rollback":
                self.phase(state, "migration")
                migration_started = True
                container = f"mf-migration-{request['deploymentId']}"
                self.runtime.compose("--profile", "tools", "run", "--name", container, "--no-deps", "migrate",
                                     image=request["image"])
                self.runtime.command(["docker", "rm", container])
            if self.runtime.database_revision() != request["databaseRevision"]:
                raise DeploymentError("Database did not reach the selected revision")
            self.phase(state, "starting")
            starting = True
            self.runtime.persist_image(request["image"])
            self.runtime.start(request["image"])
            self.phase(state, "checking")
            ready = self.runtime.ready(request["image"])
            if (
                ready.get("status") != "ready"
                or ready.get("version") != request["version"]
                or ready.get("commitSha") != request["commitSha"]
            ):
                raise DeploymentError("API readiness/version/commit verification failed")
            self.phase(state, "committing")
            state["current"] = {key: request[key] for key in Release.__required_keys__}
            history = [item for item in state.get("history", []) if item["image"] != request["image"]]
            state["history"] = [*history, state["current"]][-20:]
            state.pop("lastError", None)
            self.maintenance.unlink(missing_ok=True)
            self.phase(state, "succeeded")
            return state
        except Exception as exc:
            state["lastError"] = str(exc) if isinstance(exc, DeploymentError) else type(exc).__name__
            state["phase"] = "failed-migration" if migration_started else "failed"
            if stopped and not migration_started and not starting:
                try:
                    self.runtime.persist_image(current_image)
                    self.runtime.start(current_image)
                    self.runtime.ready(current_image)
                    self.maintenance.unlink(missing_ok=True)
                except Exception:
                    state["phase"] = "interrupted"
            elif stopped:
                try:
                    self.runtime.compose("stop", "api")
                except Exception:
                    pass
            self.store(state)
            raise DeploymentError(state["lastError"]) from None


def main() -> int:
    os.umask(0o077)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path, default=Path("/opt/mountain-fairytale"))
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--recover", action="store_true", help="Operator-reviewed recovery; never used by the timer")
    args = parser.parse_args()
    deployer = Deployer(args.project_dir)
    if args.status:
        print(encode(read_json(deployer.state_path)).decode(), end="")
        return 0
    try:
        request = fetch_request()
        if request is not None:
            deployer.apply(request, recover=args.recover)
        return 0
    except (DeploymentError, ValueError, OSError) as exc:
        logger.error("%s", str(exc) if isinstance(exc, DeploymentError) else type(exc).__name__)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
