import json

import pytest

from scripts.ci import release_catalog as catalog
from scripts.deploy.release_manifest import REPOSITORY
from tests.operations.test_pull_deploy import release, request


@pytest.fixture
def selection(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_REF", "refs/heads/master")
    monkeypatch.setenv("SELECTED_COMMIT", "a" * 40)
    monkeypatch.setenv("DEPLOY_OPERATION", "deploy")
    monkeypatch.setenv("GITHUB_ACTOR", "owner")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary.md"))
    run = {
        "status": "completed", "conclusion": "success", "head_sha": "a" * 40,
        "head_branch": "master", "event": "push", "path": ".github/workflows/backend-ci.yml",
        "repository": {"full_name": REPOSITORY},
    }
    files = {f"releases/{'a' * 40}.json": release()}
    monkeypatch.setattr(catalog, "api", lambda *_: run)
    monkeypatch.setattr(catalog, "read_file", lambda path: (files.get(path, {}), "old-sha"))
    monkeypatch.setattr(catalog, "write_file", lambda path, value, _sha="": files.update({path: value}))
    return run, files


def test_selection_writes_metadata_only_and_increments_id_even_for_rollback(selection, monkeypatch):
    _, files = selection
    files["production.json"] = request(number=7)
    monkeypatch.setenv("DEPLOY_OPERATION", "rollback")
    monkeypatch.setenv("COMPATIBLE_ROLLBACK", "true")
    catalog.select()
    selected = files["production.json"]
    assert selected["deploymentId"] == 8
    assert selected["operation"] == "rollback"
    assert selected["image"] == release()["image"]
    assert "token" not in json.dumps(selected).lower()


@pytest.mark.parametrize(("field", "value"), [
    ("event", "pull_request"), ("head_branch", "feature"), ("conclusion", "failure"),
    ("status", "in_progress"), ("path", ".github/workflows/untrusted.yml"), ("head_sha", "b" * 40),
])
def test_unverified_ci_cannot_select_production(selection, field, value):
    run, files = selection
    run[field] = value
    with pytest.raises(ValueError, match="successful master"):
        catalog.select()
    assert "production.json" not in files


def test_selection_cannot_run_from_another_branch(selection, monkeypatch):
    del selection
    monkeypatch.setenv("GITHUB_REF", "refs/heads/feature")
    with pytest.raises(ValueError, match="must run from master"):
        catalog.select()
