# Runbook: Commission a Dell PowerEdge host

| | |
| --- | --- |
| Change class | `host-baseline` |
| Playbook | [`ansible/playbooks/baseline-hosts.yml`](../../ansible/playbooks/baseline-hosts.yml) |
| Role | [`ansible/roles/dell_host_baseline/`](../../ansible/roles/dell_host_baseline/) |
| Provisioning notes | [`provisioning/dell/README.md`](../../provisioning/dell/README.md) |
| Change plan | Required for production. Use [`docs/change-plans/template.md`](../change-plans/template.md). |
| Approvers (CODEOWNERS) | `@custos-arcae/hardware-owners`, `@custos-arcae/security-reviewers` |

This runbook is the reusable procedure for the change *class*. A change plan
instantiates it for a specific device and window. Where this runbook says
"the executor", the change plan names the role.

---

## 1. Purpose

Bring a new or re-imaged Dell PowerEdge host to the Custos ARCAE baseline:
pinned firmware, hardened iDRAC, required host OS packages, kernel hardening,
and a verified storage layout. The host is then ready for the next change
class (Proxmox VE install, network onboarding, monitoring enrolment).

This runbook does **not** install Proxmox VE, configure switch ports, or
enrol the host in monitoring. Those are separate change classes with their
own runbooks.

## 2. Who may execute

| Role | May execute? | Notes |
| --- | --- | --- |
| `hardware-owners` | Yes | Primary executor. |
| `platform-leads` | Yes | Secondary executor; requires hardware-owner approval on the change plan. |
| `security-reviewers` | No (approve only) | Separation of duties: the approver is not the executor. |
| Any other team | No | |

The executor must have:

- SSH access to the control node.
- The iDRAC credentials for the target host exported in their shell
  environment. The exact variable names are taken from the host's
  `oob_controller.username_var` / `password_var` in inventory — for the lab
  hosts these are `CUSTOS_LAB_IDRAC_USER` and `CUSTOS_LAB_IDRAC_PASS`. The
  role reads them with `lookup('ansible.builtin.env', ...)` and fails closed
  if either is empty. Never in Git, never in inventory.
- Console-server access for the target host, tested independently of the
  management network.
- A signed commit identity matching the role account named in the change plan.

## 3. Prerequisites

Each item is a stop condition. If any is false, do not start.

- [ ] Asset registered with a stable `asset_id` in the asset system of record.
- [ ] Host present in inventory (`inventories/<env>/hosts.yml` and
      `host_vars/<asset-id>.yml`) with `oob_controller`, `storage`, and
      `network` blocks complete.
- [ ] Firmware baseline pinned in `group_vars/dell_hosts.yml`:
      `dell_host_baseline_firmware_catalogue.sha256` and a non-empty
      `target_version` for every component.
- [ ] Firmware share transport decided and evidence recorded. The iDRAC pulls
      `<share>/Catalog.xml` and every package itself, so:
      - **HTTPS** is fully source-verifiable and needs no attestation
        (preferred).
      - **HTTP / NFS / CIFS** can be content-verified on the control node but
        leave an identity gap; they are rejected unless
        `dell_host_baseline_firmware_source_verified=true` is set with the
        evidence below.
      - **FTP / TFTP / control-node-local** are never permitted.
      For a non-HTTPS share, record: isolated management VLAN, read-only
      export, and confirmation that the control node and the iDRAC read the
      same artifact. `verify_firmware_catalogue.py` enforces this at run time.
- [ ] Lab evidence attached to the change plan for the same role version and
      the same PowerEdge model.
- [ ] Maintenance window booked and communicated to the on-call role.
- [ ] Vendor recovery procedures cached locally for the exact firmware
      versions being applied (BIOS recovery, iDRAC reset, PERC rollback).
- [ ] Server Configuration Profile (SCP) exported from the current iDRAC
      state and stored in the restricted evidence store. This is the
      rollback artefact.
- [ ] Console path (serial-over-LAN via console server) tested and reachable
      without traversing the management switch.
- [ ] Disks confirmed empty **if** `dell_host_baseline_apply_storage` will be
      true. The attestation is recorded in the change plan.
- [ ] Change plan approved by all CODEOWNERS-required reviewers.

## 4. Expected duration

| Phase | Lab | Production (single host) |
| --- | --- | --- |
| Pre-flight | 10 min | 15 min |
| Firmware apply + reboot | 30–60 min | 45–90 min |
| iDRAC + host OS baseline | 10 min | 15 min |
| Storage verify | 5 min | 5 min |
| Verification + evidence | 15 min | 30 min |
| **Total** | **~1.5 h** | **~2.5 h** |

Firmware apply is serial (`serial: 1`). For N hosts, multiply the
production total by N and add 15 min per host for verification.

## 5. Procedure

### 5.1 Pre-flight

```bash
# From the control node, inside the maintenance window.
# <inventory-host> is the inventory alias (e.g. lab-dell-01.test), NOT the
# asset_id (e.g. LAB-DELL-0001). --limit matches inventory hostnames.
cd ansible

# 1. Confirm inventory parses and the target host is present.
ansible-inventory -i ../inventories/<env>/hosts.yml --graph dell_hosts

# 2. Confirm reachability (SSH to host OS, HTTPS to iDRAC).
ansible -i ../inventories/<env>/hosts.yml dell_hosts --limit <inventory-host> -m ping

# 3. Confirm credentials are in the environment (names from the host's
#    oob_controller.*_var; lab shown here). The values are never printed.
test -n "$CUSTOS_LAB_IDRAC_USER" && test -n "$CUSTOS_LAB_IDRAC_PASS" && echo ok

# 4. Dry run. This is the last safe checkpoint.
ansible-playbook -i ../inventories/<env>/hosts.yml \
  playbooks/baseline-hosts.yml \
  --limit <inventory-host> \
  --check --diff \
  -e custos_change_plan=docs/change-plans/<plan-id>.md
```

Capture the `--check --diff` output as evidence. Review the firmware drift
report: every component listed as drifted must have a non-empty
`target_version` and a named `recovery` procedure.

**Stop here if:**
- The dry run reports any task that would reboot the host while
  `dell_host_baseline_allow_reboot` is false.
- The firmware drift report lists a component with an empty `target_version`.
- The SCP export is missing or older than the current iDRAC firmware.
- The console path test failed.

### 5.2 Apply

```bash
# Real apply. Gates are explicit; nothing is implicit.
ansible-playbook -i ../inventories/<env>/hosts.yml \
  playbooks/baseline-hosts.yml \
  --limit <inventory-host> \
  -e custos_change_plan=docs/change-plans/<plan-id>.md \
  -e dell_host_baseline_apply=true \
  -e dell_host_baseline_apply_firmware=true \
  -e dell_host_baseline_allow_reboot=true
  # Add the two storage gates ONLY if the change plan records the
  # disks-empty attestation:
  # -e dell_host_baseline_apply_storage=true \
  # -e dell_host_baseline_storage_disks_confirmed_empty=true
```

Watch the console server in a second terminal for the entire apply. The
reboot handler will fire after firmware apply; the host should return within
`reboot_timeout` (1800 s). If it does not, treat this as a stop condition
(§7).

Before any update is submitted, the role runs
`files/verify_firmware_catalogue.py` against the fetched catalogue and fails
closed on the verdict gate `Assert the catalogue verdict is approved BEFORE any
firmware is submitted`. If that assert fires, **no firmware was submitted** —
fix the catalogue/share (or supply the non-HTTPS attestation) and re-run. For a
non-HTTPS share add `-e dell_host_baseline_firmware_source_verified=true` only
with the §3 evidence recorded in the change plan.

### 5.3 Post-apply

The playbook writes audit events to the control-node file named by
`custos_audit_log_path` (role default `/var/log/custos-arcae/audit.jsonl`,
overridable per environment). Confirm:

```bash
tail -n 20 "${custos_audit_log_path:-/var/log/custos-arcae/audit.jsonl}" | jq .
```

Expected events: `baseline-hosts.start`, `dell_host_baseline.complete`
(with `firmware_drift: 0` and `firmware_drift_source: post-activation` when
firmware was applied — the count is recomputed from the post-activation iDRAC
re-read, never from the pre-update observation), `baseline-hosts.end`.

## 6. Verification

The executor must capture all of the following as evidence and attach the
artefacts to the change plan's evidence store (not to Git).

| # | Check | Command / observation | Success criterion |
| --- | --- | --- | --- |
| 1 | Host boots and is reachable | `ssh <host> uptime` | Returns uptime, exit 0. |
| 2 | Console access works | Open serial-over-LAN session | Login prompt visible; session can be established. |
| 3 | Hardware health | `omreport chassis` (or iDRAC UI) | All components `Ok`; no amber LEDs. |
| 4 | Firmware at baseline | `omreport chassis bios` + iDRAC firmware inventory | Every component version matches `dell_host_baseline_firmware_targets[].target_version`. |
| 5 | iDRAC TLS floor | `openssl s_client -connect <iDRAC>:443 -tls1_2` | Handshake succeeds with TLS 1.2+. Repeat with `-tls1_1` — must fail. |
| 6 | IPMI over LAN disabled | `ipmitool -I lanplus -H <iDRAC> -U <user> chassis status` | Connection refused or auth failure (IPMI disabled). |
| 7 | Syslog forwarding | SIEM query for the host's iDRAC events in the last 15 min | At least one event received. |
| 8 | Storage layout | `omreport storage vdisk` | Matches inventory `storage.boot` and `storage.data`; all vdisks `Ok`. |
| 9 | Interfaces visible | `ip -br link` and `ethtool <iface>` | All expected NICs present, link up on the management and workload interfaces. |
| 10 | Kernel hardening | `sysctl --system \| grep custos` | `/etc/sysctl.d/99-custos-arcae.conf` loaded; values match `dell_host_baseline_host_os.sysctl`. |
| 11 | Forbidden packages absent | `dpkg -l telnetd rsh-server` (or rpm equivalent) | Not installed. |
| 12 | Time sync | `chronyc tracking` or `ntpq -p` | Offset < 100 ms, stratum ≤ 3. |
| 13 | Audit events | `jq` over the audit log | `dell_host_baseline.complete` present with `apply: true`. |
| 14 | Monitoring *(if already enrolled)* | Alert test from the monitoring runbook | Not applicable in this first change; skip with justification. |

Evidence format: text files or screenshots, named
`<plan-id>/<check-number>-<slug>.{txt,png}`, stored in the restricted
evidence store named in the change plan §10.3.

## 7. Stop conditions

Abort the change and escalate to the rollback owner if **any** of the
following occur. Do not retry. Do not "fix forward" without a new change
plan.

| # | Condition | Observer | Immediate action |
| --- | --- | --- | --- |
| S1 | Host does not return from reboot within `reboot_timeout` (1800 s). | Executor (console) | Capture console output. Do not power-cycle. Open the vendor case. |
| S2 | LifecycleController reports a firmware job `Failed` or `Exception`. | Executor (playbook assert) | The playbook already fails. Capture the LC log. Follow the component's `recovery` procedure. |
| S3 | iDRAC becomes unreachable mid-apply. | Executor | Switch to the console server. Do not reset iDRAC until the console shows the host state. |
| S4 | Storage drift check fails and `apply_storage` was not set. | Executor (playbook fail) | Expected behaviour. Investigate the inventory vs actual mismatch before any mutation. |
| S5 | SCP export missing or stale at pre-flight. | Executor | Abort. Re-export, re-approve the change plan, re-schedule. |
| S6 | Console path test fails at pre-flight. | Executor | Abort. There is no recovery path without an independent console. |
| S7 | Audit log shows an unexpected event source. | Executor / monitoring | Abort. Investigate for a concurrent unauthorised change. |
| S8 | Maintenance window overrun by > 50 %. | Executor | Abort, restore from SCP if the host is in a partial state, re-schedule. |
| S9 | Any credential appears in a log, diff, or console output. | Executor | Abort. Rotate the credential. Open a security incident. Do not continue the change. |

## 8. Recovery

### 8.1 Rollback (preferred)

Executable by the rollback owner without the executor present.

| # | Step | Command / action |
| --- | --- | --- |
| R1 | Confirm the host is powered off or in a known state via the console server. | Console observation. |
| R2 | Re-import the pre-change SCP to restore iDRAC settings. | `dellemc.openmanage.idrac_server_config_profile` with `command: import`, `scp_file` pointing at the export from §3, and `validate_certs: true` + `ca_path` (the 9.7.0 module uses `command`, not the removed `state`). |
| R3 | For firmware: apply the vendor-supported downgrade for the specific component, per `dell_host_baseline_firmware_targets[].recovery`. | LifecycleController → Firmware Update → select the previous version from the cached catalogue. |
| R4 | For host OS: `apt`/`dnf` history undo, or restore the sysctl file deletion (`rm /etc/sysctl.d/99-custos-arcae.conf && sysctl --system`). | SSH to host. |
| R5 | For storage: **not reversible.** If RAID was reconfigured, the rollback is a rebuild from the disks-empty state, or a restore from backup if the host carried data. | Escalate to §8.2. |
| R6 | Re-run the verification table (§6). Every check must pass against the *previous* baseline. | |
| R7 | Update the change plan status to `Rolled back`. Record the reason and the time. | |

### 8.2 Worst case

| Scenario | Path | Decision point | Time budget |
| --- | --- | --- | --- |
| BIOS bricked, host does not POST | Vendor BIOS recovery via USB (cached KB article). If recovery fails → RMA. | Console shows no POST after 2 recovery attempts. | 4 h before RMA decision. |
| iDRAC unresponsive, host healthy | iDRAC reset to defaults (physical button or `racadm racreset`). Re-apply baseline from the previous SCP. If iDRAC does not recover → RMA the iDRAC module. | iDRAC unreachable for > 30 min after reset. | 2 h before RMA decision. |
| PERC firmware failed mid-flash, vdisks inaccessible | Do **not** power-cycle. The controller may complete the flash on next boot. If the controller reports a fatal error → vendor recovery, then rebuild vdisks from scratch (data loss). | Console shows PERC error after 1 boot cycle. | 1 h before data-loss decision. |
| Host OS unbootable after package/sysctl change | Boot from the Proxmox installer rescue, chroot, undo the package/sysctl change. If the boot volume is damaged → rebuild from the Proxmox VE install runbook (not yet implemented). | Host does not reach multi-user target after 2 boot attempts. | 2 h before rebuild decision. |
| Storage reconfigured with data present | **Data loss.** Restore from PBS backup (see `docs/runbooks/restore-from-pbs.md` when implemented). Open a security incident to determine how the disks-empty attestation was wrong. | Immediately on discovery. | No budget — escalate at once. |

### 8.3 Escalation

1. Rollback owner (named in the change plan).
2. `@custos-arcae/hardware-owners` team channel.
3. `@custos-arcae/security-reviewers` if a credential leak, unauthorised
   change, or data-loss scenario is suspected.
4. Vendor support, using the case contact named in the change plan. The
   vendor case ID is recorded in the change plan §10.3, **not** in Git,
   because it may carry the personal data of the vendor engineer.

## 9. Success criteria

The change is successful when **all** of the following hold:

- Every verification check in §6 passes.
- The audit log shows `dell_host_baseline.complete` with `firmware_drift: 0`
  (when firmware was applied) and `apply: true`.
- No stop condition in §7 fired.
- The change plan status is `Executed`.
- The CHANGELOG entry (if operator-visible) is merged.
- Monitoring (when enrolled) shows the host healthy for ≥ 30 min after the
  window closes.

## 10. Compliance mapping

These are **intended** control mappings, not an attestation. They describe
which control each part of this procedure is designed to support. Two kinds
of evidence exist and must not be conflated:

- **Repository evidence** — what this repo and CI can prove on their own:
  gated apply flags, fail-closed authorization asserts, TLS verification in
  code, secret scanning, the change-plan guard, and the offline fixture run.
  This evidence is reproducible without a device.
- **Operating evidence** — what can only be proven at run time against real
  hardware in a maintenance window: the §6 verification table, firmware
  version confirmation after activation, console-path tests, and the change
  plan's signed attestations. This evidence is captured by the executor and
  stored in the restricted evidence store, **not** in Git.

A green CI run is repository evidence only. It is never sufficient on its own
to claim a control is operating effectively.

| Control | Section |
| --- | --- |
| SOC 2 CC6.1 (logical access) | §2 (who may execute), §3 (credentials never in Git) |
| SOC 2 CC7.2 (monitoring) | §5.3, §6, §7 |
| SOC 2 CC8.1 (change management) | §3 (change plan), §5 (gated apply), §8 (recovery) |
| ISO 27001 A.5.18 (access rights) | §2 |
| ISO 27001 A.8.16 (monitoring activities) | §5.3, §6 |
| ISO 27001 A.8.32 (change management) | §3, §5, §7, §8 |
| ISO 27001 A.5.24 (incident management) | §7, §8.2, §8.3 |
| ISO 27001 A.8.33 (test information) | Lab evidence prerequisite in §3 |
| GDPR Art. 5(1)(c) (data minimisation) | §2 (roles, not persons), §6 (evidence not in Git), §8.3 (vendor case not in Git) |
| GDPR Art. 32 (security of processing) | §3 (SCP export), §6 (TLS floor, IPMI disabled), §7 (credential leak stop condition) |

## 11. Revision history

| Date | Revision | Author (role) | Notes |
| --- | --- | --- | --- |
| 2026-11-24 | 1.0 | `platform-leads` | Initial runbook for the first commissioning workflow. |
| 2026-11-24 | 1.1 | `platform-leads` | Documented firmware share-type verifiability, the `dell_host_baseline_firmware_source_verified` attestation, the `verify_firmware_catalogue.py` verdict gate before submit, and the post-activation `firmware_drift_source` in the completion event. |
