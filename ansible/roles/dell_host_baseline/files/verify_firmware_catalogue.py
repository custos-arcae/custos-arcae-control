#!/usr/bin/env python3
"""Verify a Dell firmware Catalog.xml against the approved baseline.

Why this exists
---------------
``dellemc.openmanage.idrac_firmware`` makes the iDRAC pull
``<share_name>/<catalog_file_name>`` and every package it references ON ITS OWN
(audited against idrac_firmware.py 9.7.0: http(s)/ftp shares are routed through
``urlparse`` and CIFS/NFS through ``FileOnShare``; the LifecycleController
errors SYS226/SYS252 reference ``Catalog/Catalog.xml``, confirming the iDRAC
fetches the catalogue itself). The control node therefore cannot, by itself,
prove that the bytes the iDRAC downloads are identical to the bytes the control
node verified. That residual identity gap is exactly why:

  * firmware apply stays gated behind ``dell_host_baseline_hardware_validated``
    and ``dell_host_baseline_firmware_source_verified``; and
  * only HTTPS is treated as fully source-verifiable (the control node and the
    iDRAC both authenticate the same TLS server identity). HTTP/NFS/CIFS can be
    content-verified on the control node but require an explicit operator
    attestation; FTP/TFTP/local are never permitted.

What this script guarantees on the control-node side
----------------------------------------------------
  * rejects a missing, empty, malformed or ambiguous catalogue;
  * verifies every component AND version present is an approved target;
  * verifies every component carries a package identity (so we know which
    artifact the catalogue points the iDRAC at);
  * classifies the share type and reports whether it is source-verifiable.

It does NOT and cannot verify the individual package files' bytes for share
types where the iDRAC pulls independently — that is recorded as missing
evidence and gated by the attestation flag.

Usage
-----
    verify_firmware_catalogue.py --catalogue PATH --share-name NAME \
        --targets '<json list>' [--source-verified]

``--targets`` is the JSON of ``dell_host_baseline_firmware_targets`` (a list of
{component, target_version, ...}). ``--share-name`` is the firmware share exactly
as it will be passed to ``idrac_firmware.share_name``; the script classifies it
the same way the module routes it, so the role and this script never disagree
about the transport.

Exit codes: 0 = verified, 1 = rejected (verdict JSON on stdout), 2 = usage/IO
or malformed-XML error (verdict JSON on stdout where possible).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Sequence

EXIT_VERIFIED = 0
EXIT_REJECTED = 1
EXIT_ERROR = 2

# Share types the iDRAC can consume AND the control node can verify with a
# shared, authenticated server identity. Everything else is either unverifiable
# (http/nfs/cifs: the iDRAC pulls independently over a non-authenticated or
# separately-mounted transport) or never permitted (ftp/tftp: cleartext or
# mis-routed by the module; local: not reachable by the iDRAC at all).
FULLY_VERIFIABLE = {"https"}
ATTESTABLE = {"http", "nfs", "cifs"}
NEVER_PERMITTED = {"ftp", "tftp", "local", "unknown"}


def _norm(value: str) -> str:
    """Normalise an identifier for tolerant substring matching."""
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def classify_share(share_name: str) -> str:
    """Classify a firmware share the way idrac_firmware.py would route it."""
    name = (share_name or "").strip()
    lowered = name.lower()
    if lowered.startswith("https://"):
        return "https"
    if lowered.startswith("http://"):
        return "http"
    if lowered.startswith("ftp://"):
        return "ftp"
    if lowered.startswith("tftp://"):
        return "tftp"
    if name.startswith("//"):
        return "cifs"
    # NFS is written host:/export (a single slash after the host). A path with
    # no host component is a control-node-local path, which the iDRAC cannot
    # reach and the module would mis-route into the CIFS/NFS FileOnShare branch.
    if re.match(r"^[^/]+:/", name):
        return "nfs"
    if name.startswith("/"):
        return "local"
    return "unknown"


def _first_text(element: ET.Element | None, *tags: str) -> str:
    """Return the text of the first matching descendant, else ''."""
    if element is None:
        return ""
    for tag in tags:
        # Dell catalogues wrap human strings in <Display lang="...">, so the
        # text can be on the tag itself OR on its <Display> child. Both must be
        # tried unconditionally: a present-but-empty <Name> whose text lives in
        # <Name><Display> must still resolve (otherwise every name parses empty).
        for path in (tag, f"{tag}/Display"):
            node = element.find(path)
            if node is not None and (node.text or "").strip():
                return (node.text or "").strip()
    return ""


def parse_catalogue(xml_text: str) -> tuple[list[dict[str, str]], str | None]:
    """Parse a Dell Catalog.xml into component records.

    Returns (components, error). ``components`` is a list of dicts with keys
    name, version, dell_version, package_id, component_id. Handles both the
    ``<Name><Display>``/``<Version><Display>`` child form and the flat
    ``name``/``version``/``vendorVersion`` attribute form.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:  # malformed XML
        return [], f"catalogue is not well-formed XML: {exc}"

    components: list[dict[str, str]] = []
    for node in root.iter("SoftwareComponent"):
        name = _first_text(node, "Name") or node.get("name", "") or node.get("NAME", "")
        version = (
            _first_text(node, "Version")
            or node.get("vendorVersion", "")
            or node.get("version", "")
        )
        dell_version = _first_text(node, "DellVersion") or node.get("dellVersion", "")
        package_id = (
            node.get("path", "")
            or node.get("packageID", "")
            or _first_text(node, "PackageFile")
        )
        component_id = node.get("componentID", "") or node.get("releaseID", "")
        components.append(
            {
                "name": (name or "").strip(),
                "version": (version or "").strip(),
                "dell_version": (dell_version or "").strip(),
                "package_id": (package_id or "").strip(),
                "component_id": (component_id or "").strip(),
            }
        )
    return components, None


def _map_to_target(name: str, targets: Sequence[dict[str, str]]) -> list[dict[str, str]]:
    """Return the approved targets whose component name matches a catalogue name."""
    norm_name = _norm(name)
    matches: list[dict[str, str]] = []
    for target in targets:
        norm_target = _norm(target.get("component", ""))
        if norm_target and norm_target in norm_name:
            matches.append(target)
    return matches


def verify(
    components: list[dict[str, str]],
    targets: Sequence[dict[str, str]],
    source_type: str,
    source_verified: bool = False,
) -> dict[str, object]:
    """Produce a verdict dict. ``ok`` is True only when the catalogue is safe."""
    reasons: list[str] = []

    # Never-permitted transports are rejected outright, before any content
    # inspection: there is no control-node artefact that proves what the iDRAC
    # would consume over ftp/tftp, and a local path is unreachable by the iDRAC.
    if source_type in NEVER_PERMITTED:
        return {
            "ok": False,
            "source_type": source_type,
            "source_verifiable": False,
            "source_verified_attestation": bool(source_verified),
            "reasons": [
                f"share type '{source_type}' is not permitted: the iDRAC cannot "
                "be shown to consume verified bytes over this transport (ftp/tftp "
                "are cleartext or mis-routed by idrac_firmware; a local path is "
                "not reachable by the iDRAC). Use an HTTPS share."
            ],
            "total_components": len(components),
            "matched_components": [],
            "approved_not_in_catalogue": sorted(
                {t.get("component", "") for t in targets}
            ),
            "unapproved_components": [],
            "version_mismatches": [],
            "ambiguous": [],
            "missing_package_identity": [],
        }

    approved = {t.get("component", ""): t.get("target_version", "") for t in targets}
    if not any(approved.values()):
        reasons.append(
            "no approved target carries a non-empty target_version; refusing to "
            "verify against an empty baseline"
        )

    if not components:
        reasons.append("catalogue contains zero SoftwareComponent entries (empty)")

    unapproved_components: list[dict[str, str]] = []
    version_mismatches: list[dict[str, str]] = []
    missing_package_identity: list[str] = []
    # component -> set of catalogue versions seen, to detect ambiguity.
    seen_versions: dict[str, set[str]] = {}
    matched_components: set[str] = set()

    for comp in components:
        matches = _map_to_target(comp["name"], targets)
        if not matches:
            unapproved_components.append({"name": comp["name"], "version": comp["version"]})
            continue
        if len(matches) > 1:
            reasons.append(
                f"catalogue entry '{comp['name']}' maps ambiguously to multiple "
                f"approved targets: {[m.get('component') for m in matches]}"
            )
            continue
        target = matches[0]
        component = target.get("component", "")
        target_version = target.get("target_version", "")
        matched_components.add(component)
        seen_versions.setdefault(component, set()).add(comp["version"])
        if not comp["package_id"]:
            missing_package_identity.append(comp["name"])
        if comp["version"] != target_version:
            version_mismatches.append(
                {
                    "name": comp["name"],
                    "component": component,
                    "catalogue_version": comp["version"],
                    "approved_version": target_version,
                }
            )

    ambiguous = [
        {"component": component, "versions": sorted(versions)}
        for component, versions in seen_versions.items()
        if len(versions) > 1
    ]
    for entry in ambiguous:
        reasons.append(
            f"catalogue is ambiguous for '{entry['component']}': multiple versions "
            f"present {entry['versions']}; the iDRAC could consume either"
        )

    if unapproved_components:
        reasons.append(
            "catalogue advertises components that are not approved targets: "
            f"{[c['name'] for c in unapproved_components]}"
        )
    if version_mismatches:
        reasons.append(
            "catalogue versions do not match the approved targets: "
            f"{[(m['component'], m['catalogue_version'], m['approved_version']) for m in version_mismatches]}"
        )
    if missing_package_identity:
        reasons.append(
            "catalogue entries lack a package identity (path/packageID), so the "
            f"artifact the iDRAC would consume cannot be pinned: {missing_package_identity}"
        )

    approved_not_in_catalogue = sorted(set(approved) - matched_components)

    source_verifiable = source_type in FULLY_VERIFIABLE
    if source_type in ATTESTABLE and not source_verified:
        reasons.append(
            f"share type '{source_type}' cannot be integrity-verified from the "
            "control node against what the iDRAC pulls; set "
            "dell_host_baseline_firmware_source_verified=true ONLY with the "
            "documented evidence named in the runbook (isolated management "
            "VLAN, read-only export, control-node and iDRAC read the same "
            "artifact). Refusing without that attestation."
        )

    ok = not reasons
    return {
        "ok": ok,
        "source_type": source_type,
        "source_verifiable": source_verifiable,
        "source_verified_attestation": bool(source_verified),
        "reasons": reasons,
        "total_components": len(components),
        "matched_components": sorted(matched_components),
        "approved_not_in_catalogue": approved_not_in_catalogue,
        "unapproved_components": unapproved_components,
        "version_mismatches": version_mismatches,
        "ambiguous": ambiguous,
        "missing_package_identity": missing_package_identity,
    }


def _parse_targets(raw: str) -> tuple[list[dict[str, str]], str | None]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return [], f"--targets is not valid JSON: {exc}"
    if not isinstance(data, list):
        return [], "--targets must be a JSON list of {component, target_version}"
    normalised: list[dict[str, str]] = []
    for item in data:
        if not isinstance(item, dict):
            return [], "--targets entries must be objects"
        normalised.append(
            {
                "component": str(item.get("component", "")),
                "target_version": str(item.get("target_version", "")),
            }
        )
    return normalised, None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalogue", required=True, help="path to the fetched Catalog.xml")
    parser.add_argument(
        "--share-name",
        required=True,
        help="the firmware share exactly as passed to idrac_firmware.share_name",
    )
    parser.add_argument("--targets", required=True, help="JSON list of approved firmware targets")
    parser.add_argument(
        "--source-verified",
        action="store_true",
        help="operator attestation that a non-HTTPS source is trustworthy (see runbook)",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(None if argv is None else list(argv))

    targets, target_error = _parse_targets(args.targets)
    if target_error:
        print(json.dumps({"ok": False, "reasons": [target_error]}))
        return EXIT_ERROR

    source_type = classify_share(args.share_name)

    # Reject never-permitted transports before touching the filesystem: there is
    # no local catalogue artefact for ftp/tftp/local that could be trusted.
    if source_type in NEVER_PERMITTED:
        verdict = verify([], targets, source_type, args.source_verified)
        print(json.dumps(verdict, indent=2, sort_keys=True))
        return EXIT_REJECTED

    try:
        with open(args.catalogue, encoding="utf-8") as handle:
            xml_text = handle.read()
    except OSError as exc:
        print(json.dumps({"ok": False, "reasons": [f"cannot read catalogue: {exc}"]}))
        return EXIT_ERROR

    components, parse_error = parse_catalogue(xml_text)
    if parse_error:
        print(json.dumps({"ok": False, "reasons": [parse_error]}))
        return EXIT_ERROR

    verdict = verify(components, targets, source_type, args.source_verified)
    print(json.dumps(verdict, indent=2, sort_keys=True))
    return EXIT_VERIFIED if verdict["ok"] else EXIT_REJECTED


if __name__ == "__main__":
    sys.exit(main())
