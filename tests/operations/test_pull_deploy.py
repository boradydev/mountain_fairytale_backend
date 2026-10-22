import json
from pathlib import Path

import pytest

from scripts.deploy.pull_deploy import Deployer, DeploymentError, Runtime, read_json, save_json
from scripts.deploy.release_manifest import IMAGE, Release, Request, schema_metadata, validate_request


def release(character: str = "a", revision: str = "rev1") -> Release:
    return {
        "image": IMAGE + "@sha256:" + character * 64,
        "version": "1.0.0",
        "commitSha": character * 40,
        "databaseRevision": revision,
        "migrations": {"rev1": "1" * 64, **({revision: "2" * 64} if revision != "rev1" else {})},
        "ciRunId": 123,
    }


def request(selected: Release | None = None, number: int = 1, operation: str = "deploy") -> Request:
    return validate_request({
        **(selected or release()), "deploymentId": number, "operation": operation,
        "compatibleRollback": operation == "rollback", "requestedAt": "2026-10-22T12:00:00Z",
        "requestedBy": "owner",
    })


class FakeRuntime(Runtime):
    def __init__(self, project: Path) -> None:
        super().__init__(project)
        self.events: list[str] = []
        self.fail = ""
        self.revision = "rev1"
        self.current = "local-previous"
        self.images = {"local-previous": release("b"), release()["image"]: release()}

    def command(self, args: list[str], *, image: str = "", timeout: int = 2400) -> str:
        del image, timeout
        self.events.append(" ".join(args))
        return ""

    def compose(self, *args: str, image: str = "", timeout: int = 2400) -> str:
        del timeout
        self.events.append(" ".join(args))
        if "backup" in args and "run" in args and self.fail == "backup":
            raise DeploymentError("Backup failed")
        if "migrate" in args:
            if self.fail == "migration":
                raise DeploymentError("Migration failed")
            self.revision = self.images[image]["databaseRevision"]
        return ""

    def current_image(self) -> str:
        return self.current

    def inspect_release(self, selected: Release) -> None:
        del selected
        self.events.append("inspect")

    def schema(self, image: str) -> tuple[str, dict[str, str]]:
        selected = self.images[image]
        return selected["databaseRevision"], selected["migrations"]

    def database_revision(self) -> str:
        return self.revision

    def start(self, image: str) -> None:
        self.events.append("start " + image)
        self.current = image

    def ready(self, image: str) -> dict:
        if self.fail == "health":
            raise DeploymentError("Readiness failed")
        selected = self.images[image]
        return {"status": "ready", "version": selected["version"], "commitSha": selected["commitSha"]}

    def persist_image(self, image: str) -> None:
        self.events.append("persist " + image)


@pytest.fixture
def deployment(tmp_path):
    runtime = FakeRuntime(tmp_path)
    return Deployer(tmp_path, runtime), runtime


def test_success_backs_up_before_migration_and_does_not_repeat_request(deployment):
    deployer, runtime = deployment
    state = deployer.apply_locked(request())
    assert state["phase"] == "succeeded"
    assert state["current"]["image"] == release()["image"]
    backup = runtime.events.index("run --rm --no-deps backup run --category predeploy")
    migrate = next(index for index, event in enumerate(runtime.events) if "migrate" in event)
    assert runtime.events.index("stop api") < backup < migrate
    assert not deployer.maintenance.exists()
    events = list(runtime.events)
    deployer.apply_locked(request())
    assert runtime.events == events


def test_backup_failure_restarts_previous_api_without_migration_or_retries(deployment):
    deployer, runtime = deployment
    runtime.fail = "backup"
    with pytest.raises(DeploymentError, match="Backup failed"):
        deployer.apply_locked(request())
    assert runtime.current == "local-previous"
    assert not any("migrate" in event for event in runtime.events)
    assert not deployer.maintenance.exists()
    assert read_json(deployer.state_path)["phase"] == "failed"
    events = list(runtime.events)
    deployer.apply_locked(request())
    assert runtime.events == events


def test_changed_applied_migration_is_blocked_before_api_stops(deployment):
    deployer, runtime = deployment
    selected = release()
    selected["migrations"]["rev1"] = "f" * 64
    with pytest.raises(DeploymentError, match="changed or removed"):
        deployer.apply_locked(request(selected))
    assert "stop api" not in runtime.events


def test_migration_failure_keeps_api_stopped_and_requires_review(deployment):
    deployer, runtime = deployment
    runtime.fail = "migration"
    with pytest.raises(DeploymentError, match="Migration failed"):
        deployer.apply_locked(request())
    assert deployer.maintenance.exists()
    assert not any(event.startswith("start ") for event in runtime.events)
    assert read_json(deployer.state_path)["phase"] == "failed-migration"
    with pytest.raises(DeploymentError, match="operator review"):
        deployer.apply_locked(request(number=2))


def test_health_failure_after_migration_never_downgrades_database_automatically(deployment):
    deployer, runtime = deployment
    runtime.fail = "health"
    with pytest.raises(DeploymentError, match="Readiness failed"):
        deployer.apply_locked(request())
    assert runtime.events[-1] == "stop api"
    assert deployer.maintenance.exists()
    assert not any("downgrade" in event for event in runtime.events)


def test_compatible_rollback_uses_known_image_and_skips_migrations(deployment):
    deployer, runtime = deployment
    current, previous = release(), release("b")
    runtime.current = current["image"]
    runtime.images[previous["image"]] = previous
    save_json(deployer.state_path, {"phase": "succeeded", "current": current, "history": [previous, current]})
    state = deployer.apply_locked(request(previous, operation="rollback"))
    assert state["current"] == previous
    assert state["previous"] == current
    assert not any("migrate" in event for event in runtime.events)
    assert "run --rm --no-deps backup run --category predeploy" in runtime.events


def test_rollback_of_changed_schema_is_blocked_before_stopping_api(deployment):
    deployer, runtime = deployment
    current, previous = release("a", "rev2"), release("b")
    runtime.current, runtime.revision = current["image"], "rev2"
    runtime.images[current["image"]] = current
    save_json(deployer.state_path, {"current": current, "history": [previous, current]})
    with pytest.raises(DeploymentError, match="changes the database schema"):
        deployer.apply_locked(request(previous, operation="rollback"))
    assert "stop api" not in runtime.events


def test_unknown_rollback_image_is_blocked(deployment):
    deployer, runtime = deployment
    with pytest.raises(DeploymentError, match="never been successfully deployed"):
        deployer.apply_locked(request(operation="rollback"))
    assert "stop api" not in runtime.events


def test_interrupted_deploy_is_not_repeated_after_restart(deployment):
    deployer, runtime = deployment
    save_json(deployer.state_path, {"phase": "migration", "lastAttemptedId": 1})
    state = deployer.apply_locked(request())
    assert state["phase"] == "interrupted"
    assert not runtime.events
    with pytest.raises(DeploymentError, match="operator review"):
        deployer.apply_locked(request(number=2))


@pytest.mark.parametrize(("field", "value"), [
    ("image", "evil.example/image:latest"), ("image", IMAGE + ":latest"),
    ("deploymentId", True), ("ciRunId", 0), ("operation", "shell"), ("commitSha", "main"),
])
def test_invalid_request_cannot_control_docker(field, value):
    data = dict(request())
    data[field] = value
    with pytest.raises(ValueError, match="Invalid"):
        validate_request(data)


def test_rollback_requires_explicit_data_compatibility_confirmation():
    data = dict(request(operation="rollback"))
    data["compatibleRollback"] = False
    with pytest.raises(ValueError, match="confirmation"):
        validate_request(data)


def test_schema_checksums_detect_sql_rewrite_with_same_revision(tmp_path):
    folder = tmp_path / "src/common/infra/db/postgres/alembic/migrations/versions/initial"
    folder.mkdir(parents=True)
    (folder / "migration.py").write_text("revision: str = 'rev1'\ndown_revision: str | None = None\n")
    sql = folder / "upgrade.sql"
    sql.write_text("CREATE TABLE example(id int);")
    revision, before = schema_metadata(tmp_path)
    sql.write_text("CREATE TABLE example(id text);")
    after_revision, after = schema_metadata(tmp_path)
    assert revision == after_revision == "rev1"
    assert before != after


def test_status_never_contains_server_environment_values(deployment, monkeypatch):
    deployer, _ = deployment
    monkeypatch.setenv("POSTGRES_PASSWORD", "do-not-publish-this")
    deployer.apply_locked(request())
    assert "do-not-publish-this" not in json.dumps(read_json(deployer.state_path))
