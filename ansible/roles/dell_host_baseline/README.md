# Role: `dell_host_baseline`

Baselines a Dell PowerEdge host for the Custos ARCAE estate: firmware,
iDRAC settings, host OS packages, kernel hardening, and storage layout.

This role is the apply step of the commissioning workflow. The operator
procedure lives in [`docs/runbooks/commission-dell-host.md`](../../../docs/runbooks/commission-dell-host.md).

## Inputs

All inputs come from inventory (`group_vars` / `host_vars`). The role never
hard-codes site values.

| Variable | Required | Source | Notes |
| --- | --- | --- | --- |
| `asset_id` | yes | `host_vars` | Stable asset identifier. Renaming is a change-plan event. |
| `oob_controller.address` | yes | `host_vars` | iDRAC IP or hostname. |
| `oob_controller.username_var` | yes | `host_vars` | **Name** of the env var holding the iDRAC username. Never the value. |
| `oob_controller.password_var` | yes | `host_vars` | **Name** of the env var holding the iDRAC password. Never the value. |
| `storage.boot`, `storage.data` | yes | `host_vars` | Expected RAID layout. See `inventories/lab/hosts.yml`. |
| `dell_host_baseline_firmware_targets` | yes | `group_vars` | Pinned firmware versions per component. Empty `target_version` blocks apply. |
| `dell_host_baseline_firmware_catalogue.sha256` | yes (for apply) | `group_vars` | SHA-256 of the tested `Catalog.cab`. |
| `dell_host_baseline_idrac_ca_path` | yes | `group_vars` / `-e` | Trusted CA bundle for iDRAC TLS. Every iDRAC call sets `validate_certs: true`; an empty `ca_path` fails the role closed. |
| `custos_environment` | yes | `group_vars/all.yml` | `lab` or `production`. |
| `custos_change_plan` | yes (production) | `-e` flag | Path to the filed change plan. |

## Gates

Every mutating step is behind a gate. Defaults are safe.

| Gate | Default | Effect when true |
| --- | --- | --- |
| `dell_host_baseline_apply` | `false` | Global apply flag. No mutation of any kind happens unless this is true. |
| `dell_host_baseline_apply_firmware` | `false` | Allow firmware updates. Requires pinned catalogue + target versions. |
| `dell_host_baseline_firmware_source_verified` | `false` | Operator attestation for a **non-HTTPS** firmware share (HTTP/NFS/CIFS). `files/verify_firmware_catalogue.py` rejects those transports unless this is true, because the iDRAC pulls the catalogue and packages itself and the control node cannot prove byte identity over them. HTTPS needs no attestation; FTP/TFTP/local are never permitted. Does not by itself enable apply. |
| `dell_host_baseline_allow_reboot` | `false` | Allow the reboot handler to fire. Asserted **before** a reboot-requiring firmware update is submitted, not after. |
| `dell_host_baseline_apply_storage` | `false` | Allow RAID reconfiguration. |
| `dell_host_baseline_storage_disks_confirmed_empty` | `false` | Operator attestation required before any RAID mutation. |
| `dell_host_baseline_hardware_validated` | `false` | Master hardware-evidence gate. Firmware **and** storage apply both refuse to run while this is false, because neither path has yet been validated against real lab hardware. Set it true only via a change plan that carries the lab evidence (see "Known limitations"). |
| `dell_host_baseline_offline` | `false` | CI/test seam. Suppresses every device call and substitutes fixture data so the local authorization / drift / storage-contract / audit logic can run with `ansible_connection: local`. Asserted mutually exclusive with all apply gates. |

A production run without a filed `custos_change_plan` is rejected by the
playbook's pre-tasks before this role is reached.

## Outputs

- Firmware drift report (always, even in check mode).
- Storage drift report (always, even in check mode).
- Before any firmware is submitted, `files/verify_firmware_catalogue.py`
  verifies the fetched `Catalog.xml` against `dell_host_baseline_firmware_targets`
  and the verdict gate (`Assert the catalogue verdict is approved BEFORE any
  firmware is submitted`) fails the run unless the catalogue is fully approved.
  It rejects empty, malformed or ambiguous catalogues, unapproved components,
  version mismatches, entries with no package identity, and any non-HTTPS share
  without the `dell_host_baseline_firmware_source_verified` attestation. The
  verifier runs on the control node and never contacts a device.
- After a firmware apply, the role re-reads the firmware inventory and
  asserts every component reached its pinned `target_version` **before** the
  completion event is recorded. A mismatch fails the run; success is never
  recorded on the strength of the apply job alone. The completion event reports
  `firmware_drift` recomputed from that **post-activation** observation
  (`firmware_drift_source: post-activation`), never the pre-update drift.
- Audit events written to `custos_audit_log_path` on the control node as one
  JSON object per line (built via `to_json`).
- Handler notifications: `restart idrac`, `reboot host`, `reload systemd`,
  `restart time service`, `apply sysctl`.

## Verification

After a successful apply, the executor must capture:

1. `omreport chassis` output (or equivalent iDRAC inventory) showing all
   components at the pinned firmware versions.
2. `omreport storage vdisk` showing the expected RAID layout with all
   virtual disks `Ok`.
3. Host OS reachable over SSH on the management interface.
4. iDRAC reachable over HTTPS with TLS ≥ 1.2 and IPMI-over-LAN disabled.
5. Audit log entry `dell_host_baseline.complete` with `apply=true` and
   `firmware_drift=0`.

Evidence is attached to the change plan, not committed to Git.

## Rollback

| Step | Rollback |
| --- | --- |
| Firmware | Vendor-supported downgrade for the exact component. Named in `dell_host_baseline_firmware_targets[].recovery`. Some components (BIOS, LifecycleController) may not support downgrade — recovery is forward repair or RMA. |
| iDRAC settings | Re-apply the previous Server Configuration Profile (SCP) exported before the change. The runbook requires an SCP export as a pre-flight step. |
| Host OS packages | `apt`/`dnf` history undo. The role does not remove packages that were present before; it only ensures the baseline set. |
| sysctl | Delete `/etc/sysctl.d/99-custos-arcae.conf` and `sysctl --system`. |
| Storage | **Not reversible.** RAID reconfiguration destroys data. This is why the apply is doubly gated and the runbook requires a disks-empty attestation. |

## Dependencies

- Ansible ≥ 2.17.
- Collections pinned in [`ansible/requirements.yml`](../../../ansible/requirements.yml):
  `dellemc.openmanage`, `ansible.posix`, `community.general`,
  `community.crypto`.
- `cabextract` on the control node (for firmware catalogue extraction).
- Out-of-band network reachability from the control node to every iDRAC.
- SSH reachability to the host OS (for the host-OS baseline section).

## Known limitations

- The role assumes iDRAC9 with LifecycleController enabled. iDRAC8 and
  iDRAC10 are not tested; adding support requires an ADR.
- The role talks to iDRAC only through the modules it actually uses:
  `idrac_firmware_info`, `idrac_firmware`, `idrac_storage_volume`,
  `idrac_attributes`, `idrac_timezone_ntp`, and `idrac_syslog` (all audited
  against `dellemc.openmanage` 9.7.0). It does **not** use OpenManage
  Enterprise (`ome_*`) modules.
- Firmware apply is serial (`serial: 1` in the playbook). Parallel firmware
  updates across a rack are not supported and would void the recovery
  assumptions.
- **Firmware and storage apply are hardware-unvalidated and therefore
  disabled by default** behind `dell_host_baseline_hardware_validated=false`.
  Only the read-only / verification paths run today. Before either mutation
  path is enabled, the following lab tests must pass on the target PowerEdge
  model and the evidence attached to a change plan:
  - *Firmware*: the pinned `Catalog.cab`/`Catalog.xml` (SHA-256 match) is
    published on an iDRAC-reachable share; `verify_firmware_catalogue.py`
    confirms the catalogue carries only approved components at the approved
    versions with a package identity each; the share transport is either HTTPS
    (fully verifiable) or an attested HTTP/NFS/CIFS export
    (`dell_host_baseline_firmware_source_verified=true` with the runbook
    evidence); `idrac_firmware` applies only after that verdict gate passes;
    the post-activation re-read confirms every `target_version`; and the reboot
    handler fires only under `dell_host_baseline_allow_reboot`.
  - *Storage (PERC)*: the supported PERC controller is confirmed
    (`RAID.Slot.*`), the **real** drive IDs are discovered via
    `idrac_storage_volume` `state=view` (the inventory IDs are format
    placeholders today), occupied-disk detection is proven so a non-empty
    disk is never claimed, and the RAID recovery procedure is exercised.
    Until then storage stays verification-only.

## Compliance mapping

| Control | How this role satisfies it |
| --- | --- |
| SOC 2 CC8.1 (change management) | Gates default off; production requires a filed change plan; audit events written per run. |
| ISO 27001 A.12.1.2 (change management) | Same as above; rollback documented per step. |
| ISO 27001 A.9.4 (access control) | Credentials resolved from the operator's environment, never stored in inventory or Git. |
| GDPR Art. 5(1)(c) (data minimisation) | No personal data in inventory, role variables, or audit events. Ownership is by team/role. |
| GDPR Art. 32 (security of processing) | TLS floor enforced on iDRAC; IPMI-over-LAN disabled; syslog forwarded to SIEM. |
