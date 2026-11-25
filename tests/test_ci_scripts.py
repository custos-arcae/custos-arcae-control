"""Tests for the CI policy scripts under .github/scripts/.

These load the scripts directly by file path (they are workflow helpers, not
part of the installed package) and exercise every decision branch against fake
fixtures, with no git repository and no real secret scanner required.

Coverage:
  * detect_secrets_check.evaluate / main — clean, findings-present, and
    scanner-error (non-zero exit, empty output, unparseable JSON).
  * check_change_plan.evaluate — no production, missing plan, deleted-only
    plan, covering plan, uncovered asset, unrelated change class, cancelled.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / ".github" / "scripts"


def _load(module_name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS_DIR / f"{module_name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


detect_secrets_check = _load("detect_secrets_check")
check_change_plan = _load("check_change_plan")


# --- detect-secrets fixtures -------------------------------------------------

CLEAN_SCAN = '{"version": "1.5.0", "results": {}, "plugins_used": []}'
FINDINGS_SCAN = (
    '{"version": "1.5.0", "results": '
    '{"inventories/lab/hosts.yml": [{"line_number": 42, "type": "High Entropy String"}]}}'
)


def test_detect_secrets_clean_passes() -> None:
    code, findings, error = detect_secrets_check.evaluate(CLEAN_SCAN, 0)
    assert code == detect_secrets_check.EXIT_CLEAN
    assert findings == []
    assert error is None


def test_detect_secrets_findings_fail() -> None:
    code, findings, error = detect_secrets_check.evaluate(FINDINGS_SCAN, 0)
    assert code == detect_secrets_check.EXIT_FINDINGS
    assert error is None
    assert findings == [("inventories/lab/hosts.yml", 42, "High Entropy String")]


def test_detect_secrets_scanner_nonzero_exit_fails() -> None:
    code, findings, error = detect_secrets_check.evaluate("", 3)
    assert code == detect_secrets_check.EXIT_SCANNER_ERROR
    assert findings == []
    assert error is not None and "code 3" in error


def test_detect_secrets_empty_output_fails() -> None:
    code, _, error = detect_secrets_check.evaluate("   \n", 0)
    assert code == detect_secrets_check.EXIT_SCANNER_ERROR
    assert error is not None and "no output" in error


def test_detect_secrets_unparseable_output_fails() -> None:
    code, _, error = detect_secrets_check.evaluate("Traceback (most recent call last):", 0)
    assert code == detect_secrets_check.EXIT_SCANNER_ERROR
    assert error is not None and "not valid JSON" in error


def test_detect_secrets_missing_results_key_fails() -> None:
    code, _, error = detect_secrets_check.evaluate('{"version": "1.5.0"}', 0)
    assert code == detect_secrets_check.EXIT_SCANNER_ERROR
    assert error is not None and "results" in error


def test_detect_secrets_main_propagates_findings(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        detect_secrets_check, "run_scan", lambda scanner, exclude: (FINDINGS_SCAN, 0, "")
    )
    assert detect_secrets_check.main([]) == detect_secrets_check.EXIT_FINDINGS


def test_detect_secrets_main_propagates_scanner_error(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(detect_secrets_check, "run_scan", lambda scanner, exclude: ("", 2, "boom"))
    assert detect_secrets_check.main([]) == detect_secrets_check.EXIT_SCANNER_ERROR


def test_detect_secrets_main_clean(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        detect_secrets_check, "run_scan", lambda scanner, exclude: (CLEAN_SCAN, 0, "")
    )
    assert detect_secrets_check.main([]) == detect_secrets_check.EXIT_CLEAN


# --- change-plan fixtures ----------------------------------------------------

PROD_HOST = "inventories/production/lt-vilnius-01/host_vars/LT-VIL-0001.yml"
DELL_ROLE = "ansible/roles/dell_host_baseline/defaults/main.yml"


def _plan(change_class: str, status: str, assets: str = "LT-VIL-0001") -> str:
    return (
        "# Change plan: commission host\n\n"
        "## 0. Identification\n\n"
        "| Field | Value |\n"
        "| --- | --- |\n"
        f"| Change class | {change_class} |\n"
        "| Environment | production/lt-vilnius-01 |\n"
        f"| Status | {status} |\n\n"
        "## 3.1 Target devices\n\n"
        "| Asset ID | Hostname |\n"
        "| --- | --- |\n"
        f"| {assets} | lt-vil-0001.test |\n"
    )


def test_change_plan_no_production_is_ok() -> None:
    ok, reasons = check_change_plan.evaluate(
        [("M", "ansible/roles/dell_host_baseline/tasks/main.yml")], {}, {}
    )
    assert ok is True
    assert reasons == []


def test_change_plan_missing_plan_fails() -> None:
    ok, reasons = check_change_plan.evaluate(
        [("M", PROD_HOST), ("M", DELL_ROLE)], {}, {PROD_HOST: "asset_id: LT-VIL-0001\n"}
    )
    assert ok is False
    assert any("no docs/change-plans" in r for r in reasons)


def test_change_plan_deleted_only_fails() -> None:
    ok, reasons = check_change_plan.evaluate(
        [("M", PROD_HOST), ("D", "docs/change-plans/20261124-old.md")],
        {},
        {PROD_HOST: "asset_id: LT-VIL-0001\n"},
    )
    assert ok is False
    assert any("deletions" in r for r in reasons)


def test_change_plan_covering_passes() -> None:
    plan = "docs/change-plans/20261124-commission.md"
    ok, reasons = check_change_plan.evaluate(
        [("M", PROD_HOST), ("M", DELL_ROLE), ("A", plan)],
        {plan: _plan("host-baseline", "Approved")},
        {PROD_HOST: "asset_id: LT-VIL-0001\n"},
    )
    assert ok is True, reasons
    assert reasons == []


def test_change_plan_uncovered_asset_fails() -> None:
    plan = "docs/change-plans/20261124-commission.md"
    ok, reasons = check_change_plan.evaluate(
        [("M", PROD_HOST), ("M", DELL_ROLE), ("A", plan)],
        {plan: _plan("host-baseline", "Approved", assets="SOME-OTHER-9999")},
        {PROD_HOST: "asset_id: LT-VIL-0001\n"},
    )
    assert ok is False
    assert any("covers affected asset" in r for r in reasons)


def test_change_plan_unrelated_class_fails() -> None:
    plan = "docs/change-plans/20261124-commission.md"
    ok, reasons = check_change_plan.evaluate(
        [("M", PROD_HOST), ("M", DELL_ROLE), ("A", plan)],
        {plan: _plan("monitoring", "Approved")},
        {PROD_HOST: "asset_id: LT-VIL-0001\n"},
    )
    assert ok is False
    assert any("change class" in r for r in reasons)


def test_change_plan_cancelled_fails() -> None:
    plan = "docs/change-plans/20261124-commission.md"
    ok, reasons = check_change_plan.evaluate(
        [("M", PROD_HOST), ("M", DELL_ROLE), ("A", plan)],
        {plan: _plan("host-baseline", "Cancelled")},
        {PROD_HOST: "asset_id: LT-VIL-0001\n"},
    )
    assert ok is False
    assert any("Cancelled" in r for r in reasons)


def test_change_plan_template_does_not_count() -> None:
    ok, reasons = check_change_plan.evaluate(
        [("M", PROD_HOST), ("M", "docs/change-plans/template.md")],
        {"docs/change-plans/template.md": _plan("host-baseline", "Approved")},
        {PROD_HOST: "asset_id: LT-VIL-0001\n"},
    )
    assert ok is False
    assert any("no docs/change-plans" in r for r in reasons)
