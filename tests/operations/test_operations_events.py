from types import SimpleNamespace

from scripts.deploy import operations_check
from scripts.deploy.operations_check import backup_condition, disk_condition


def test_disk_thresholds_and_recovery():
    assert disk_condition(20, 100) == "ok"
    assert disk_condition(19, 100) == "warning"
    assert disk_condition(10, 100) == "warning"
    assert disk_condition(9, 100) == "critical"
    assert disk_condition(50, 100) == "ok"


def test_backup_state_reports_errors_but_never_missing_schedule():
    assert backup_condition({"coveredSlot": "2020-01-01"}) == "ok"
    assert backup_condition({"lastError": {"reason": "private-detail"}}) == "backup_failed"
    assert backup_condition({"cleanupRequired": True}) == "cleanup_failed"
    assert backup_condition({"cleanupRequired": False}) == "ok"


def test_stopped_backup_is_not_an_uptime_alert(tmp_path, monkeypatch):
    (tmp_path / ".deploy").mkdir()
    monkeypatch.setattr(operations_check, "environment", lambda _: {"OPERATIONS_SENTRY_DSN": "configured"})
    monkeypatch.setattr(operations_check.shutil, "disk_usage", lambda _: SimpleNamespace(free=80, total=100))
    monkeypatch.setattr(operations_check.subprocess, "run", lambda *_args, **_kwargs: SimpleNamespace(returncode=1))
    sent = []
    monkeypatch.setattr(operations_check, "report", lambda *args: sent.append(args))
    operations_check.check(tmp_path)
    assert sent == []
