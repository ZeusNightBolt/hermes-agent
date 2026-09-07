"""Fork-only runtime overrides (girnarholdings fork).

This module is FORK-OWNED: upstream never has it, so a rebase of the fork
delta over upstream can never conflict here. Hot upstream files (cron/jobs.py,
cron/scheduler.py) reference this module through a tiny one-line shim; if a
rebase drops the shim, the loss is detected by the fork's own gate tests
(tests/cron/test_cron_inactivity_timeout.py) instead of silently changing
runtime behavior.

cron timeout ladder (decided 2026-09-05, operator): env
HERMES_CRON_TIMEOUT (legacy bridge, highest precedence, 0=unlimited) →
profile config ``cron.agent_inactivity_timeout_seconds`` → 600s default.
Our config estate (master + all 12 profiles) sets 1800; upstream's env-only
resolution would ignore it.
"""

from __future__ import annotations

import os

_DEFAULT_CRON_INACTIVITY_TIMEOUT = 600.0


def cron_inactivity_timeout_seconds() -> float:
    """Resolve agent-cron inactivity from env, then profile config, then default."""
    raw = os.getenv("HERMES_CRON_TIMEOUT", "").strip()
    if raw:
        try:
            return float(raw)
        except (ValueError, TypeError):
            return _DEFAULT_CRON_INACTIVITY_TIMEOUT
    try:
        from hermes_cli.config import load_config

        config = load_config() or {}
        cron_config = config.get("cron", {}) if isinstance(config, dict) else {}
        configured = cron_config.get("agent_inactivity_timeout_seconds")
        if configured is not None:
            return float(configured)
    except (ImportError, TypeError, ValueError):
        pass
    return _DEFAULT_CRON_INACTIVITY_TIMEOUT
