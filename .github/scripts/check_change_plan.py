#!/usr/bin/env python3
"""Require a change plan ADDED OR UPDATED by the PR that covers the change.

Policy (AGENTS.md §6)
---------------------
When a PR touches ``inventories/production/**`` it must also add or modify a
``docs/change-plans/YYYYMMDD-<slug>.md`` that:

1. is *added or modified* by this PR (a deleted plan does not count);
2. names every affected ``asset_id`` (coverage of the affected assets);
3. declares a change class matching the proposed action implied by the changed
   role / provisioning paths; and
4. is not marked ``Cancelled``.

If no such plan exists the check fails with a specific reason (missing,
deleted-only, uncovered asset, unrelated class, or cancelled).

This is a *repository-level* guard. It cannot verify that the plan was approved
by the right humans — that is enforced in GitHub via CODEOWNERS + branch
protection (see docs/adr/0001 and .github/CODEOWNERS). The decision logic is a
set of pure functions so ``tests/test_ci_scripts.py`` can exercise every branch
against fake fixtures without a git repository.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path

CHANGE_PLAN_RE = re.compile(r"^docs/change-plans/\d{8}-.+\.md$")
TEMPLATE_PLAN = "docs/change-plans/template.md"
ASSET_ID_RE = re.compile(r"asset_id:\s*['\"]?([A-Za-z0-9._-]+)")

# Changed path prefix -> the change class token the plan must declare.
CLASS_BY_PATH: tuple[tuple[tuple[str, ...], str], ...] = (
    (("ansible/roles/dell_host_baseline/", "provisioning/dell/"), "host-baseline"),
    (("ansible/roles/proxmox_ve/", "provisioning/proxmox-ve/"), "proxmox-ve"),
    (("ansible/roles/proxmox_backup/",), "proxmox-backup"),
    (("ansible/roles/management_network/",), "management-network"),
    (("ansible/roles/switch_baseline/",), "switch"),
    (("ansible/roles/monitoring/",), "monitoring"),
)

ADDED_OR_MODIFIED = {"A", "M", "C", "R", "T"}


def is_change_plan(path: str) -> bool:
    return bool(CHANGE_PLAN_RE.match(path)) and path != TEMPLATE_PLAN


def classify(name_status: Sequence[tuple[str, str]]) -> dict[str, list[tuple[str, str]]]:
    """Split ``git diff --name-status`` rows into plans / production / other."""
    plans: list[tuple[str, str]] = []
    production: list[tuple[str, str]] = []
    other: list[tuple[str, str]] = []
    for status, path in name_status:
        code = status[:1]  # R100 -> R
        if is_change_plan(path):
            plans.append((code, path))
        elif path.startswith("inventories/production/"):
            production.append((code, path))
        else:
            other.append((code, path))
    return {"plans": plans, "production": production, "other": other}


def affected_assets(production_contents: dict[str, str]) -> set[str]:
    """Asset IDs declared by the added/modified production inventory files."""
    assets: set[str] = set()
    for content in production_contents.values():
        assets.update(ASSET_ID_RE.findall(content or ""))
    return assets


def required_classes(changed_paths: Iterable[str]) -> set[str]:
    """Change classes implied by the non-plan paths this PR touches."""
    classes: set[str] = set()
    for path in changed_paths:
        for prefixes, token in CLASS_BY_PATH:
            if any(path.startswith(p) for p in prefixes):
                classes.add(token)
    return classes


def _table_cell(text: str, row_label: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and row_label.lower() in stripped.lower():
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if len(cells) >= 2:
                return cells[1]
    return ""


def parse_plan(text: str) -> dict[str, str]:
    return {
        "change_class": _table_cell(text, "Change class"),
        "status": _table_cell(text, "Status"),
        "text": text or "",
    }


def evaluate(
    name_status: Sequence[tuple[str, str]],
    plan_contents: dict[str, str],
    production_contents: dict[str, str],
) -> tuple[bool, list[str]]:
    """Return ``(ok, reasons)``. ``reasons`` is empty when ``ok`` is True."""
    grouped = classify(name_status)
    production = grouped["production"]

    if not production:
        # Nothing production-affecting; the workflow gates this anyway.
        return True, []

    reasons: list[str] = []

    live_plans = [(s, p) for (s, p) in grouped["plans"] if s in ADDED_OR_MODIFIED]
    deleted_only = grouped["plans"] and not live_plans
    if not live_plans:
        if deleted_only:
            reasons.append(
                "the only change-plan edits in this PR are deletions; a deleted "
                "plan does not authorize a production change"
            )
        else:
            reasons.append("no docs/change-plans/YYYYMMDD-*.md was added or modified by this PR")
        return False, reasons

    assets = affected_assets(production_contents)
    required = required_classes(p for _, p in grouped["production"] + grouped["other"])
    parsed = {path: parse_plan(plan_contents.get(path, "")) for _, path in live_plans}

    # Reject plans whose status is Cancelled — they cannot authorize anything.
    usable = {p: d for p, d in parsed.items() if "cancelled" not in d["status"].lower()}
    cancelled = [p for p, d in parsed.items() if "cancelled" in d["status"].lower()]
    if cancelled and not usable:
        reasons.append(
            f"the added/modified change plan(s) {sorted(cancelled)} are marked Cancelled"
        )
        return False, reasons

    # Coverage: every affected asset must appear in at least one usable plan.
    uncovered = sorted(a for a in assets if not any(a in d["text"] for d in usable.values()))
    if uncovered:
        reasons.append(f"no added/modified change plan covers affected asset(s): {uncovered}")

    # Action: at least one usable plan must declare a required change class.
    if required:
        matched = any(
            any(re.search(rf"\b{re.escape(cls)}\b", d["change_class"]) for cls in required)
            for d in usable.values()
        )
        if not matched:
            reasons.append(
                f"no added/modified change plan declares a change class matching the "
                f"proposed action {sorted(required)} (declared: "
                f"{[d['change_class'] for d in usable.values()]})"
            )

    return (not reasons), reasons


def _read_name_status(base: str, head: str) -> list[tuple[str, str]]:
    out = subprocess.run(  # noqa: S603
        ["git", "diff", "--name-status", base, head],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    rows: list[tuple[str, str]] = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            rows.append((parts[0], parts[-1]))  # renames: take the new path
    return rows


def _read_name_status_file(path: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            rows.append((parts[0].strip(), parts[-1].strip()))
    return rows


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", help="base SHA of the PR")
    parser.add_argument("--head", help="head SHA of the PR")
    parser.add_argument(
        "--name-status-file",
        help="read TAB-separated '<status>\\t<path>' rows from FILE instead of git "
        "(used by tests and offline reproduction)",
    )
    parser.add_argument("--repo", default=".", help="repository root for reading file contents")
    args = parser.parse_args(None if argv is None else list(argv))

    if args.name_status_file:
        name_status = _read_name_status_file(args.name_status_file)
    elif args.base and args.head:
        name_status = _read_name_status(args.base, args.head)
    else:
        print("::error::provide --base/--head or --name-status-file", file=sys.stderr)
        return 2

    grouped = classify(name_status)
    repo = Path(args.repo)

    def contents_of(rows: Sequence[tuple[str, str]]) -> dict[str, str]:
        result: dict[str, str] = {}
        for status, path in rows:
            if status[:1] not in ADDED_OR_MODIFIED:
                continue
            fp = repo / path
            if fp.is_file():
                result[path] = fp.read_text(encoding="utf-8", errors="replace")
        return result

    plan_contents = contents_of(grouped["plans"])
    production_contents = contents_of(grouped["production"])

    ok, reasons = evaluate(name_status, plan_contents, production_contents)
    if ok:
        print("Change-plan requirement satisfied.")
        return 0
    for reason in reasons:
        print(f"::error::change plan check failed: {reason}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
