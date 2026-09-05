"""Fork-only guard tests: cron inactivity-timeout ladder (girnarholdings fork).

These tests pin the fork's timeout-ladder feature (env HERMES_CRON_TIMEOUT →
profile config ``cron.agent_inactivity_timeout_seconds`` → 600s default) and
its wiring through the one-line shim in cron/jobs.py.

WHY THIS FILE IS FORK-ONLY NAMED: on every upstream rebase, hot files
(cron/jobs.py, cron/scheduler.py) may be resolved upstream-wins and silently
drop the fork feature while upstream's own tests still pass ("phantom green").
Upstream never has this file, so it can never conflict — but if the feature is
dropped, these tests fail and the updater's gate turns red, refusing to open
the PR.

Decided 2026-09-05 (operator).
"""

import os
import sys
from pathlib import Path

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

_REPO_ROOT = Path(__file__).parent.parent.parent

_EXPECTED_CONFIG_TEXT = "cron:\n  agent_inactivity_timeout_seconds: 1800\n"


def _write_profile_config(text: str = _EXPECTED_CONFIG_TEXT) -> None:
    """Write cron agent_inactivity_timeout_seconds into the sandboxed profile config."""
    (Path(os.environ["HERMES_HOME"]) / "config.yaml").write_text(text)


# ---------------------------------------------------------------------------
# Wiring guards: source-text assertions (catch an upstream-wins rebase that
# drops the shim while the module still imports fine).
# ---------------------------------------------------------------------------


def test_shim_present_in_jobs():
    """The one-line fork shim must still exist in cron/jobs.py SOURCE text."""
    jobs_source = (_REPO_ROOT / "cron" / "jobs.py").read_text(encoding="utf-8")
    assert "fork_overrides" in jobs_source, (
        "The fork shim in cron/jobs.py was lost in an upstream rebase "
        "(upstream-wins resolution dropped the fork feature). "
        "Re-run the fork feature attach step to restore "
        "'from cron.fork_overrides import cron_inactivity_timeout_seconds "
        "as _cron_inactivity_timeout_seconds' in cron/jobs.py."
    )


def test_scheduler_references_fork_ladder():
    """cron/scheduler.py must still reference the fork timeout ladder."""
    scheduler_source = (_REPO_ROOT / "cron" / "scheduler.py").read_text(
        encoding="utf-8"
    )
    assert (
        "_cron_inactivity_timeout_seconds" in scheduler_source
        or "fork_overrides" in scheduler_source
    ), (
        "cron/scheduler.py no longer references the fork timeout ladder "
        "(_cron_inactivity_timeout_seconds / fork_overrides) — the fork "
        "feature was lost in an upstream rebase. Re-run the fork feature "
        "attach step."
    )


# ---------------------------------------------------------------------------
# Behavior guards: the ladder itself, via the fork-owned module.
# ---------------------------------------------------------------------------


def test_ladder_via_fork_overrides_module(monkeypatch, tmp_path):
    """Ladder precedence via cron.fork_overrides directly:
    env → profile config → 600.0 default (env 0 = unlimited, garbage = 600)."""
    from cron import fork_overrides

    # 1. No env + profile config 1800 → 1800.0
    monkeypatch.delenv("HERMES_CRON_TIMEOUT", raising=False)
    _write_profile_config()
    assert fork_overrides.cron_inactivity_timeout_seconds() == 1800.0

    # 2. env=900 overrides config → 900.0
    monkeypatch.setenv("HERMES_CRON_TIMEOUT", "900")
    assert fork_overrides.cron_inactivity_timeout_seconds() == 900.0

    # 3. env=0 = unlimited → 0.0
    monkeypatch.setenv("HERMES_CRON_TIMEOUT", "0")
    assert fork_overrides.cron_inactivity_timeout_seconds() == 0.0

    # 4. env=garbage (invalid) → falls back to 600.0 default
    monkeypatch.setenv("HERMES_CRON_TIMEOUT", "garbage")
    assert fork_overrides.cron_inactivity_timeout_seconds() == 600.0

    # 5. No env + empty config dir (no config.yaml) → 600.0 default
    monkeypatch.delenv("HERMES_CRON_TIMEOUT", raising=False)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "empty-home"))
    assert fork_overrides.cron_inactivity_timeout_seconds() == 600.0


def test_ladder_via_jobs_shim(monkeypatch, tmp_path):
    """Same four ladder cases through cron.jobs._cron_inactivity_timeout_seconds
    — proves the shim wiring end-to-end (jobs.py still re-exports the fork
    implementation, not a stale upstream body)."""
    from cron import jobs

    assert (
        jobs._cron_inactivity_timeout_seconds
        is not None
    )
    # The shim must be the FORK implementation, not a jobs.py-local body.
    from cron.fork_overrides import cron_inactivity_timeout_seconds as _fork_impl

    assert jobs._cron_inactivity_timeout_seconds is _fork_impl

    # 1. No env + profile config 1800 → 1800.0
    monkeypatch.delenv("HERMES_CRON_TIMEOUT", raising=False)
    _write_profile_config()
    assert jobs._cron_inactivity_timeout_seconds() == 1800.0

    # 2. env=900 overrides config → 900.0
    monkeypatch.setenv("HERMES_CRON_TIMEOUT", "900")
    assert jobs._cron_inactivity_timeout_seconds() == 900.0

    # 3. env=0 = unlimited → 0.0
    monkeypatch.setenv("HERMES_CRON_TIMEOUT", "0")
    assert jobs._cron_inactivity_timeout_seconds() == 0.0

    # 4. env=garbage (invalid) → falls back to 600.0 default
    monkeypatch.setenv("HERMES_CRON_TIMEOUT", "garbage")
    assert jobs._cron_inactivity_timeout_seconds() == 600.0

    # 5. No env + empty config dir (no config.yaml) → 600.0 default
    monkeypatch.delenv("HERMES_CRON_TIMEOUT", raising=False)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "empty-home"))
    assert jobs._cron_inactivity_timeout_seconds() == 600.0
