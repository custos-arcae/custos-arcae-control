#!/usr/bin/env python3
"""Fail the build on ANY detect-secrets finding OR scanner error.

Why this exists
---------------
The previous inline workflow logic swallowed failures. It ran::

    detect-secrets scan ... > /tmp/secrets.json
    if python - <<'PY'
        ... sys.exit(1) on findings ...
    PY
    then
        echo "No secrets detected."
    fi

Because the findings check was the *condition* of an ``if``, a non-zero exit
(a finding) only skipped the ``then`` branch; it never failed the job. A
scanner crash that produced empty or non-JSON output was likewise ignored.
Both cases passed silently.

This module makes three outcomes explicit and testable:

* clean scan         -> exit 0
* one or more findings -> exit 1
* scanner error (non-zero exit, empty output, or unparseable JSON) -> exit 2

The decision logic lives in :func:`evaluate`, a pure function that takes the
scanner's stdout and return code. ``tests/test_ci_scripts.py`` exercises it
against fake fixtures for all three cases without invoking the real scanner.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Iterable, Sequence

# Directories/files that legitimately contain high-entropy or secret-looking
# strings (virtualenvs, packaging metadata, coverage data, the change-plan
# template's placeholder table, and the offline CI fixtures).
DEFAULT_EXCLUDE_FILES: tuple[str, ...] = (
    r"\.venv/",
    r"\.git/",
    r".*\.egg-info/",
    r"\.coverage",
    r"\.mypy_cache/",
    r"\.pytest_cache/",
    r"\.ruff_cache/",
    r"docs/change-plans/template\.md",
    r"ansible/\.ansible/",
)

EXIT_CLEAN = 0
EXIT_FINDINGS = 1
EXIT_SCANNER_ERROR = 2


def evaluate(
    scan_stdout: str, returncode: int
) -> tuple[int, list[tuple[str, int, str]], str | None]:
    """Decide pass/fail from a detect-secrets scan result.

    Returns ``(exit_code, findings, error_message)`` where ``findings`` is a
    list of ``(path, line_number, plugin_type)`` tuples and ``error_message``
    is set only for a scanner error.
    """
    if returncode != 0:
        return EXIT_SCANNER_ERROR, [], f"detect-secrets exited with code {returncode}"

    if not scan_stdout.strip():
        return EXIT_SCANNER_ERROR, [], "detect-secrets produced no output"

    try:
        data = json.loads(scan_stdout)
    except (ValueError, json.JSONDecodeError) as exc:
        return EXIT_SCANNER_ERROR, [], f"detect-secrets output was not valid JSON: {exc}"

    if not isinstance(data, dict) or "results" not in data:
        return EXIT_SCANNER_ERROR, [], "detect-secrets output missing the 'results' key"

    findings: list[tuple[str, int, str]] = []
    results = data.get("results") or {}
    for path, items in results.items():
        for item in items or []:
            findings.append(
                (path, int(item.get("line_number", 1)), str(item.get("type", "unknown")))
            )

    if findings:
        return EXIT_FINDINGS, findings, None
    return EXIT_CLEAN, [], None


def run_scan(scanner: str, exclude_files: Sequence[str]) -> tuple[str, int, str]:
    """Invoke the detect-secrets scanner and capture its output."""
    cmd: list[str] = [scanner, "scan"]
    for pattern in exclude_files:
        cmd += ["--exclude-files", pattern]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)  # noqa: S603
    return proc.stdout, proc.returncode, proc.stderr


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scanner",
        default="detect-secrets",
        help="detect-secrets executable (default: detect-secrets on PATH)",
    )
    parser.add_argument(
        "--exclude-files",
        action="append",
        default=None,
        help="extra exclude regex; defaults are always applied",
    )
    args = parser.parse_args(None if argv is None else list(argv))

    exclude_files = list(DEFAULT_EXCLUDE_FILES)
    if args.exclude_files:
        exclude_files.extend(args.exclude_files)

    stdout, returncode, stderr = run_scan(args.scanner, exclude_files)
    code, findings, error = evaluate(stdout, returncode)

    if error is not None:
        print(f"::error::secret scanner error: {error}", file=sys.stderr)
        if stderr.strip():
            print(stderr.strip(), file=sys.stderr)
        return code

    if findings:
        for path, line, secret_type in findings:
            print(f"::error file={path},line={line}::potential secret ({secret_type})")
        print(f"::error::{len(findings)} potential secret(s) detected", file=sys.stderr)
        return code

    print("No secrets detected.")
    return EXIT_CLEAN


if __name__ == "__main__":
    raise SystemExit(main())
