"""Regression tests for the operator entry point: baseline-hosts.yml.

These drive the REAL playbook (ansible/playbooks/baseline-hosts.yml) against
offline fixtures and assert that controller-side preflight stops an invalid or
unauthorized run BEFORE any remote connection is attempted.

They complement tests/test_ci_scripts.py (CI policy scripts) and the role-level
offline fixture (ansible/tests/offline/baseline-offline.yml), which covers the
role's internal behaviour. The tests here cover the PLAYBOOK's preflight
ordering, its production gate, and its explicit fact-gathering step.

"Before any remote connection" is proven two ways:
  * the PLAY RECAP reports `unreachable=0` (the fixtures point at unroutable
    RFC 5737 addresses over SSH, so a regression that reached the connection
    phase would report `unreachable>=1`); and
  * the explicit "Gather facts from the target" task never appears in the
    output for the rejected runs.

Requires ansible-playbook on PATH; skipped otherwise (e.g. in the Python-only
CI job). The Ansible CI job installs Ansible and runs these for real.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
ANSIBLE_DIR = REPO_ROOT / "ansible"
PLAYBOOK = "playbooks/baseline-hosts.yml"
OFFLINE_INVENTORY = "tests/offline/inventory.yml"
BAD_INVENTORY = "tests/offline/preflight-bad-inventory.yml"
PROD_INVENTORY = "tests/offline/preflight-production.yml"
SETUP_TASK = "Gather facts from the target"
OFFLINE_AUDIT = Path("/tmp/custos-ci-offline-audit.jsonl")

ANSIBLE_PLAYBOOK = shutil.which("ansible-playbook")

pytestmark = pytest.mark.skipif(
    ANSIBLE_PLAYBOOK is None,
    reason="ansible-playbook is not installed; run in the Ansible CI job",
)


def _env() -> dict[str, str]:
    env = os.environ.copy()
    env["ANSIBLE_CONFIG"] = str(ANSIBLE_DIR / "ansible.cfg")
    env["ANSIBLE_ROLES_PATH"] = str(ANSIBLE_DIR / "roles")
    # Never prompt for a become password in CI; the offline fixtures do not
    # escalate (become is derived from `not offline`).
    env["ANSIBLE_BECOME_ASK_PASS"] = "False"
    env["ANSIBLE_LOCALHOST_WARNING"] = "False"
    env["ANSIBLE_RETRY_FILES_ENABLED"] = "False"
    env["ANSIBLE_STDOUT_CALLBACK"] = "default"
    return env


def _run(inventory: str, extra: list[str] | None = None) -> subprocess.CompletedProcess[str]:
    cmd = [str(ANSIBLE_PLAYBOOK), "-i", inventory, PLAYBOOK, *(extra or [])]
    return subprocess.run(  # noqa: S603 - fixed argv, no shell
        cmd,
        cwd=ANSIBLE_DIR,
        env=_env(),
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )


def _recap(output: str) -> dict[str, int]:
    """Extract unreachable/failed/ok counts from the PLAY RECAP line."""
    match = re.search(r"unreachable=(\d+).*?failed=(\d+)", output, re.S)
    assert match is not None, f"no PLAY RECAP in output:\n{output[-2000:]}"
    return {"unreachable": int(match.group(1)), "failed": int(match.group(2))}


def test_invalid_inventory_stops_before_any_remote_connection() -> None:
    proc = _run(BAD_INVENTORY)
    assert proc.returncode != 0, "invalid inventory must fail"
    assert "Assert inventory contract" in proc.stdout
    recap = _recap(proc.stdout + proc.stderr)
    # Failed on the controller-side assert; never attempted SSH.
    assert recap["failed"] >= 1
    assert recap["unreachable"] == 0, f"preflight must run before SSH:\n{proc.stdout[-2000:]}"
    # The explicit fact-gathering task (first remote action) never ran.
    assert SETUP_TASK not in proc.stdout


def test_unauthorized_production_scope_stops_before_any_remote_connection() -> None:
    # The fixture supplies a VALID change-plan filename on purpose: a matching
    # filename alone must NOT authorize a production execution.
    proc = _run(PROD_INVENTORY)
    assert proc.returncode != 0, "production must be refused in this phase"
    assert "Refuse production commissioning during the read-only pilot phase" in proc.stdout
    recap = _recap(proc.stdout + proc.stderr)
    assert recap["failed"] >= 1
    assert recap["unreachable"] == 0, f"preflight must run before SSH:\n{proc.stdout[-2000:]}"
    assert SETUP_TASK not in proc.stdout


def test_offline_entrypoint_runs_preflight_then_gathers_facts() -> None:
    # Happy path: a valid lab fixture in offline mode must pass preflight, then
    # gather facts explicitly, then run the role and write valid JSONL audit
    # events (start / complete / end) with no privilege escalation.
    OFFLINE_AUDIT.unlink(missing_ok=True)
    proc = _run(OFFLINE_INVENTORY)
    assert proc.returncode == 0, f"offline entry point must succeed:\n{proc.stdout[-3000:]}"
    recap = _recap(proc.stdout + proc.stderr)
    assert recap["failed"] == 0
    assert recap["unreachable"] == 0
    # The explicit fact-gathering step ran (facts are needed for the audit ts).
    assert SETUP_TASK in proc.stdout

    assert OFFLINE_AUDIT.exists(), "audit log was not written"
    events = [json.loads(line) for line in OFFLINE_AUDIT.read_text().splitlines() if line.strip()]
    names = {e.get("event") for e in events}
    assert "baseline-hosts.start" in names
    assert "dell_host_baseline.complete" in names
    assert "baseline-hosts.end" in names
