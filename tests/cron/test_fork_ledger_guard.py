"""Fork-only ledger guard tests (girnarholdings).

Ported from the fork's superseded executions.py delta: the upstream
implementation now provides call-time path resolution and deterministic
connection close, so these tests pin that behavior against regression.
File name is fork-only: it survives upstream-wins test replacement.
"""

import os
import sqlite3


import pytest


def _point_ledger(monkeypatch, tmp_path):
    import cron.executions as executions

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    return executions


def _fork_ledger_path(executions):
    """Call-time ledger path (matches module resolution order)."""
    import hermes_constants
    return executions.EXECUTIONS_FILE or (
        hermes_constants.get_hermes_home().resolve() / "cron" / "executions.db")


def test_recovery_does_not_mark_other_live_owner_unknown(monkeypatch, tmp_path):
    executions = _point_ledger(monkeypatch, tmp_path)
    record = executions.create_execution("other-live", source="builtin")
    with sqlite3.connect(_fork_ledger_path(executions)) as conn:
        conn.execute(
            "UPDATE executions SET process_id=?, pid=? WHERE id=?",
            ("another-import", os.getpid(), record["id"]),
        )

    assert executions.recover_interrupted_executions() == 0
    assert executions.latest_execution("other-live")["status"] == "claimed"


def test_recovery_rejects_recycled_pid(monkeypatch, tmp_path):
    executions = _point_ledger(monkeypatch, tmp_path)
    record = executions.create_execution("recycled", source="builtin")
    with sqlite3.connect(_fork_ledger_path(executions)) as conn:
        conn.execute(
            "UPDATE executions SET process_id=?, process_started_at=? WHERE id=?",
            ("old-import", -1, record["id"]),
        )

    assert executions.recover_interrupted_executions() == 1
    assert executions.latest_execution("recycled")["status"] == "unknown"


def test_ledger_path_follows_hermes_home_at_call_time(monkeypatch, tmp_path):
    """Test fixture rows must land in the per-test tempdir, never the real home.

    Regression: the ledger path used to be resolved once at module import,
    BEFORE pytest's hermetic fixture monkeypatched HERMES_HOME, so any suite
    that exercised the scheduler wrote its fixture rows (j1..j10, monitor-job,
    tg-job, ...) into the developer's production ``~/.hermes/cron/executions.db``.
    """
    import cron.executions as executions  # imported long before this test runs

    stale_home = tmp_path / "stale-home"
    fresh_home = tmp_path / "fresh-home"
    monkeypatch.setenv("HERMES_HOME", str(stale_home))
    monkeypatch.setenv("HERMES_HOME", str(fresh_home))

    record = executions.create_execution("isolation-probe", source="builtin")

    assert not (stale_home / "cron" / "executions.db").exists()
    ledger = fresh_home.resolve() / "cron" / "executions.db"
    assert _fork_ledger_path(executions) == ledger
    assert ledger.exists()
    with sqlite3.connect(ledger) as conn:
        rows = conn.execute(
            "SELECT job_id FROM executions WHERE id=?", (record["id"],)
        ).fetchall()
    assert [row[0] for row in rows] == ["isolation-probe"]
