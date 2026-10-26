import json
from copy import deepcopy

from scripts.deploy.information_events import observe


def api(started="2026-10-26T10:00:00Z"):
    return {"id": "a" * 64, "startedAt": started, "health": "healthy", "version": "1.0.0", "commitSha": "a" * 40}


def backup(marker="a"):
    return {"api_backup": {"lastSuccess": {
        "at": "2026-10-26T10:00:00Z", "manifestKey": f"private-prefix/daily/20261026T100000Z-{marker * 32}.json",
    }}}


def test_initial_observation_is_quiet_then_start_and_success_are_info_and_deduplicated():
    sent, events = {}, []
    def emit(event):
        events.append(event)
        return True
    observe(sent, api(), {}, backup(), emit, "test")
    assert events == []
    observe(sent, api("2026-10-26T11:00:00Z"), {}, backup("b"), emit, "test")
    assert [e["message"] for e in events] == ["api_started", "backup_succeeded"]
    assert all(e["level"] == "info" for e in events)
    assert "private-prefix" not in json.dumps(events)
    observe(sent, api("2026-10-26T11:00:00Z"), {}, backup("b"), emit, "test")
    assert len(events) == 2


def test_first_future_deploy_is_reported_and_raw_error_environment_never_leak():
    sent, events = {}, []
    def emit(event):
        events.append(event)
        return True
    observe(sent, {}, {}, {}, emit, "test")
    outcome = {"event": "api_deploy_failed", "deploymentId": 1, "version": "1.1.0",
               "phase": "migration", "lastError": "secret-token", "environment": {"password": "secret"}}
    observe(sent, {}, {"lastLifecycle": outcome}, {}, emit, "test")
    assert events[0]["message"] == "api_deploy_failed"
    assert events[0]["contexts"]["lifecycle"]["phase"] == "migration"
    assert "secret" not in json.dumps(events)
    outcome.update(event="api_deployed", deploymentId=2, operation="rollback", previousVersion="1.1.0")
    observe(sent, {}, {"lastLifecycle": outcome}, {}, emit, "test")
    assert events[-1]["message"] == "api_deployed"
    assert events[-1]["contexts"]["lifecycle"]["operation"] == "rollback"


def test_delivery_failure_keeps_marker_and_retry_uses_same_event_id():
    sent, events = {}, []
    observe(sent, api(), {}, {}, lambda _: True, "test")
    baseline = deepcopy(sent)
    observe(sent, api("2026-10-26T11:00:00Z"), {}, {}, lambda event: events.append(event) or False, "test")
    assert sent == baseline
    observe(sent, api("2026-10-26T11:00:00Z"), {}, {}, lambda event: events.append(event) or True, "test")
    assert events[0]["event_id"] == events[1]["event_id"]


def test_missing_or_unhealthy_container_produces_no_event():
    sent, events = {}, []
    observe(sent, api(), {}, {}, lambda _: True, "test")
    observe(sent, {}, {}, {}, lambda event: events.append(event) or True, "test")
    observe(sent, {**api("2026-10-26T11:00:00Z"), "health": "unhealthy"}, {}, {},
            lambda event: events.append(event) or True, "test")
    assert events == []
