"""Offline tests for the Dell firmware catalogue verifier.

These tests exercise ``ansible/roles/dell_host_baseline/files/
verify_firmware_catalogue.py`` against synthetic Catalog.xml fixtures and
assert that every rejected case fails closed BEFORE the role could submit a
firmware update. No device, network or credential is touched: the verifier is a
pure function of (catalogue bytes, share name, approved targets).

The final structural test asserts, against the real ``tasks/firmware.yml``, that
the verdict gate is positioned before the ``idrac_firmware`` submit task, so a
rejected catalogue can never reach the update.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "ansible/roles/dell_host_baseline/files/verify_firmware_catalogue.py"
FIXTURES = REPO_ROOT / "ansible/tests/offline/firmware"
FIRMWARE_TASKS = REPO_ROOT / "ansible/roles/dell_host_baseline/tasks/firmware.yml"

# The approved baseline the fixtures are written against. Component matching in
# the verifier is a normalised substring match, so "iDRAC" matches the catalogue
# display name "iDRAC9 Firmware", "NIC" matches "Broadcom NIC Firmware", etc.
TARGETS = [
    {"component": "BIOS", "target_version": "2.11.2"},
    {"component": "iDRAC", "target_version": "6.00.02.00"},
    {"component": "LifecycleController", "target_version": "5.10.10.00"},
    {"component": "PERC", "target_version": "5.11.0-0004"},
    {"component": "NIC", "target_version": "22.9.7"},
]
TARGETS_JSON = json.dumps(TARGETS)


def _load_module():
    spec = importlib.util.spec_from_file_location("verify_firmware_catalogue", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


vfc = _load_module()


def _run(fixture: str, share_name: str, source_verified: bool = False):
    """Invoke main() and return (exit_code, verdict_dict)."""
    argv = [
        "--catalogue",
        str(FIXTURES / fixture),
        "--share-name",
        share_name,
        "--targets",
        TARGETS_JSON,
    ]
    if source_verified:
        argv.append("--source-verified")
    code = vfc.main(argv)
    return code


def _verdict(fixture: str, share_name: str, source_verified: bool = False) -> dict:
    """Run the verifier capturing stdout, returning the parsed verdict JSON."""
    import contextlib
    import io

    argv = [
        "--catalogue",
        str(FIXTURES / fixture),
        "--share-name",
        share_name,
        "--targets",
        TARGETS_JSON,
    ]
    if source_verified:
        argv.append("--source-verified")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        vfc.main(argv)
    return json.loads(buf.getvalue())


# --- share classification ----------------------------------------------------


@pytest.mark.parametrize(
    ("share_name", "expected"),
    [
        ("https://fw.lab.test/dell", "https"),
        ("http://fw.lab.test/dell", "http"),
        ("ftp://fw.lab.test/dell", "ftp"),
        ("tftp://fw.lab.test/dell", "tftp"),
        ("//files.lab.test/dell", "cifs"),
        ("192.0.2.50:/srv/dell", "nfs"),
        ("files.lab.test:/srv/dell", "nfs"),
        ("/tmp/local-only", "local"),
        ("", "unknown"),
        ("nonsense", "unknown"),
    ],
)
def test_classify_share_matches_idrac_firmware_routing(share_name, expected):
    assert vfc.classify_share(share_name) == expected


# --- catalogue content verdicts (over a fully-verifiable HTTPS share) ---------


def test_approved_catalogue_over_https_is_verified():
    assert _run("catalog-approved.xml", "https://fw.lab.test/dell") == vfc.EXIT_VERIFIED
    verdict = _verdict("catalog-approved.xml", "https://fw.lab.test/dell")
    assert verdict["ok"] is True
    assert verdict["source_verifiable"] is True
    assert sorted(verdict["matched_components"]) == [
        "BIOS",
        "LifecycleController",
        "NIC",
        "PERC",
        "iDRAC",
    ]
    assert verdict["reasons"] == []


def test_empty_catalogue_is_rejected():
    assert _run("catalog-empty.xml", "https://fw.lab.test/dell") == vfc.EXIT_REJECTED
    verdict = _verdict("catalog-empty.xml", "https://fw.lab.test/dell")
    assert verdict["ok"] is False
    assert any("zero SoftwareComponent" in r for r in verdict["reasons"])


def test_unapproved_component_is_rejected():
    code = _run("catalog-unapproved-component.xml", "https://fw.lab.test/dell")
    assert code == vfc.EXIT_REJECTED
    verdict = _verdict("catalog-unapproved-component.xml", "https://fw.lab.test/dell")
    assert verdict["ok"] is False
    assert verdict["unapproved_components"], "expected a named unapproved component"


def test_unapproved_version_is_rejected():
    code = _run("catalog-unapproved-version.xml", "https://fw.lab.test/dell")
    assert code == vfc.EXIT_REJECTED
    verdict = _verdict("catalog-unapproved-version.xml", "https://fw.lab.test/dell")
    assert verdict["ok"] is False
    assert verdict["version_mismatches"], "expected a version mismatch record"


def test_ambiguous_catalogue_is_rejected():
    code = _run("catalog-ambiguous.xml", "https://fw.lab.test/dell")
    assert code == vfc.EXIT_REJECTED
    verdict = _verdict("catalog-ambiguous.xml", "https://fw.lab.test/dell")
    assert verdict["ok"] is False
    assert verdict["ambiguous"], "expected an ambiguity record"


def test_missing_package_identity_is_rejected():
    code = _run("catalog-missing-package-id.xml", "https://fw.lab.test/dell")
    assert code == vfc.EXIT_REJECTED
    verdict = _verdict("catalog-missing-package-id.xml", "https://fw.lab.test/dell")
    assert verdict["ok"] is False
    assert verdict["missing_package_identity"], "expected a missing-identity record"


def test_malformed_catalogue_fails_closed_with_error_exit():
    # Malformed XML is an error (exit 2), never a silent pass or empty verdict.
    assert _run("catalog-malformed.xml", "https://fw.lab.test/dell") == vfc.EXIT_ERROR
    verdict = _verdict("catalog-malformed.xml", "https://fw.lab.test/dell")
    assert verdict["ok"] is False
    assert any("not well-formed XML" in r for r in verdict["reasons"])


def test_missing_catalogue_file_fails_closed():
    code = _run("catalog-does-not-exist.xml", "https://fw.lab.test/dell")
    assert code == vfc.EXIT_ERROR


# --- share-type gate (the identity gap between control node and iDRAC) --------


@pytest.mark.parametrize(
    "share_name",
    ["http://fw.lab.test/dell", "192.0.2.50:/srv/dell", "//files.lab.test/dell"],
)
def test_attestable_share_rejected_without_attestation(share_name):
    assert _run("catalog-approved.xml", share_name) == vfc.EXIT_REJECTED
    verdict = _verdict("catalog-approved.xml", share_name)
    assert verdict["ok"] is False
    assert verdict["source_verifiable"] is False
    assert any("cannot be integrity-verified" in r for r in verdict["reasons"])


@pytest.mark.parametrize(
    "share_name",
    ["http://fw.lab.test/dell", "192.0.2.50:/srv/dell", "//files.lab.test/dell"],
)
def test_attestable_share_accepted_with_attestation(share_name):
    assert _run("catalog-approved.xml", share_name, source_verified=True) == vfc.EXIT_VERIFIED
    verdict = _verdict("catalog-approved.xml", share_name, source_verified=True)
    assert verdict["ok"] is True
    assert verdict["source_verified_attestation"] is True


@pytest.mark.parametrize(
    "share_name",
    ["ftp://fw.lab.test/dell", "tftp://fw.lab.test/dell", "/tmp/local", "nonsense"],
)
def test_never_permitted_share_rejected_even_with_attestation(share_name):
    # Attestation must NOT rescue a cleartext/unreachable transport.
    assert _run("catalog-approved.xml", share_name, source_verified=True) == vfc.EXIT_REJECTED
    verdict = _verdict("catalog-approved.xml", share_name, source_verified=True)
    assert verdict["ok"] is False
    assert any("not permitted" in r for r in verdict["reasons"])


# --- structural guarantee in the real role ------------------------------------


def test_verdict_gate_precedes_firmware_submit_task():
    """No rejected catalogue may reach the idrac_firmware submit task.

    Asserts, against the real tasks/firmware.yml, that the verdict assert is
    defined before the submit task, so a rejected/errored catalogue fails the
    play first.
    """
    text = FIRMWARE_TASKS.read_text(encoding="utf-8")
    gate = text.index("Assert the catalogue verdict is approved BEFORE any firmware is submitted")
    submit = text.index("dellemc.openmanage.idrac_firmware")
    verify = text.index("Verify the fetched catalogue against the approved firmware baseline")
    assert verify < gate < submit, (
        "the catalogue verifier and its verdict gate must both precede the "
        "idrac_firmware submit task"
    )


def test_never_permitted_transport_is_also_rejected_by_the_role():
    """The role rejects FTP/TFTP at the share assert too (defense in depth)."""
    text = FIRMWARE_TASKS.read_text(encoding="utf-8")
    assert "Reject cleartext or unreachable firmware share transports" in text
    assert "is not match('^(ftp|tftp)://')" in text
