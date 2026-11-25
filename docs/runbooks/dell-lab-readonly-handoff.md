# Operator handoff: read-only Dell PowerEdge lab test

| | |
| --- | --- |
| Purpose | Operator-led, **read-only** inspection of ONE spare PowerEdge in the Lithuanian pilot lab. |
| Change class | `host-baseline` (read-only subset) |
| Playbook | [`ansible/playbooks/baseline-hosts.yml`](../../ansible/playbooks/baseline-hosts.yml) |
| Role | [`ansible/roles/dell_host_baseline/`](../../ansible/roles/dell_host_baseline/) |
| Full procedure | [`docs/runbooks/commission-dell-host.md`](commission-dell-host.md) |
| Approvers (CODEOWNERS) | `@custos-arcae/hardware-owners`, `@custos-arcae/security-reviewers` |

> **This handoff authorises observation only.** It does **not** authorise
> firmware application, RAID changes, reboots, iDRAC setting changes, or any
> production run. Those stay disabled and are listed as *later* tests in §7.

---

## 1. What was verified before this handoff (repository evidence)

This is what the repository and its offline CI can prove **without a device**.
It is not operating evidence — see `commission-dell-host.md` §10 for the
distinction.

| Item | Value | How it was verified |
| --- | --- | --- |
| Repository revision | **no first commit exists yet** (branch `main`, no `HEAD`) | `git rev-parse HEAD` → *does not have any commits yet*. Record the real revision here once the maintainer creates the initial commit: `TODO(platform-leads): <commit-sha>` |
| Role version | `2.0.0` | `dell_host_baseline_role_version` in `defaults/main.yml` |
| Python | `3.12.16` | pinned toolchain `/tmp/custos-ci-venv` |
| ansible-core | `2.17.14` (package `ansible==10.5.0`) | `ansible --version`, `.github/workflows/validate.yml` |
| `dellemc.openmanage` | `9.7.0` | `ansible/requirements.yml` |
| ansible-lint | `26.6.0`, profile `production` | `ansible-lint --profile production` → *0 failure(s), 0 warning(s)* |
| Entry-point preflight | invalid inventory and unauthorized production scope stop **before** any remote connection (`unreachable=0`) | `tests/test_entrypoint_preflight.py` (3 passed) |
| Firmware catalogue verifier | approved passes; empty / unapproved-component / unapproved-version / ambiguous / missing-package-id / malformed / FTP / TFTP / local / non-HTTPS-without-attestation all reject before submit | `tests/test_firmware_catalogue.py` (30 passed) |

### Values only the operator can supply (placeholders)

Per `AGENTS.md` §1.5 these are **never** invented. Fill them from the physical
device and the change plan before the test:

| Field | Placeholder |
| --- | --- |
| Server model | `TODO(hardware-owners): <PowerEdge model, e.g. R650>` |
| Service tag / asset_id | `TODO(hardware-owners): <service-tag>` / `TODO(hardware-owners): <asset-id>` |
| iDRAC generation & firmware version | `TODO(hardware-owners): <iDRAC9 x.xx.xx.xx>` |
| BIOS version | `TODO(hardware-owners): <bios-version>` |
| PERC controller model & firmware | `TODO(hardware-owners): <PERC model, RAID.Slot.*, firmware>` |
| iDRAC management address | `TODO(hardware-owners): <idrac-host>` (inventory `oob_controller.address`) |
| Console-server port | `TODO(hardware-owners): <console-host>:<port>` |
| iDRAC CA / pinned certificate path | `TODO(hardware-owners): <ca-path>` (inventory `dell_host_baseline_idrac_ca_path`) |
| Restricted evidence store location | `TODO(platform-leads): <evidence-store-path-or-URL>` |

---

## 2. Preconditions (each is a stop condition — if false, do not start)

- [ ] The spare PowerEdge is **not** in production service and carries no data
      you cannot afford to lose. This test only reads, but confirm anyway.
- [ ] Independent console access is available and **tested without traversing
      the management network** (serial-over-LAN via the console server, or a
      directly attached keyboard/monitor).
- [ ] The iDRAC is reachable over HTTPS from the control node.
- [ ] A trusted iDRAC TLS anchor exists: the site CA bundle or the pinned iDRAC
      self-signed certificate (public cert only — never a private key).
- [ ] The iDRAC read-only credentials are exported in the operator's shell
      (`CUSTOS_LAB_IDRAC_USER`, `CUSTOS_LAB_IDRAC_PASS` for lab). Values are
      never written to inventory, Git, or the evidence store.
- [ ] The target host exists in `inventories/lab/hosts.yml` under `dell_hosts`
      with a complete `oob_controller` block.
- [ ] The pinned toolchain is installed (`ansible-galaxy install -r
      ansible/requirements.yml`).

---

## 3. Read-only lab checklist

Run every step from the control node. **No step below passes an apply gate.**
Capture the output of each numbered step into the restricted evidence store
(§6), named `<plan-or-test-id>/<step>-<slug>.txt`.

### 3.1 Independent console access

- [ ] Open a serial-over-LAN (or direct) console session to the spare.
- [ ] Confirm the session works while the management network path is
      unavailable (unplug/disable the management link, or use a physically
      separate console server path).
- [ ] **Expected:** login prompt or POST screen visible; session can be
      established and typed into.
- [ ] Record: console-server host/port, whether SOL or direct, and the time the
      independent-path test succeeded.

### 3.2 Trusted iDRAC TLS

- [ ] Install/point at the CA or pinned certificate:
      `dell_host_baseline_idrac_ca_path` in `inventories/lab/group_vars/dell_hosts.yml`.
- [ ] Verify the handshake from the control node:
      ```bash
      openssl s_client -connect <idrac-host>:443 -tls1_2 -CAfile <ca-path> </dev/null
      # must succeed and show the expected iDRAC certificate subject
      openssl s_client -connect <idrac-host>:443 -tls1_1 </dev/null
      # must FAIL — TLS 1.1 and below are refused
      ```
- [ ] **Expected:** TLS 1.2+ handshake succeeds against the trusted anchor;
      TLS 1.1 fails; the certificate subject/SAN matches the recorded iDRAC.
- [ ] The role always calls iDRAC with `validate_certs: true` and a non-empty
      `ca_path`; an empty `ca_path` fails the role closed (no silent downgrade).

### 3.3 Firmware inventory (read-only)

Run the operator entry point with **no apply gates** — the default. This only
gathers facts and reports drift:

```bash
cd ansible
# 1. Inventory parses and the spare is present.
ansible-inventory -i ../inventories/lab/hosts.yml --graph dell_hosts

# 2. Credentials are present (names only; values never printed).
test -n "$CUSTOS_LAB_IDRAC_USER" && test -n "$CUSTOS_LAB_IDRAC_PASS" && echo ok

# 3. READ-ONLY baseline run. No -e dell_host_baseline_apply*, no allow_reboot.
#    --limit targets exactly ONE inventory host (the spare), never a group.
ansible-playbook -i ../inventories/lab/hosts.yml \
  playbooks/baseline-hosts.yml \
  --limit <inventory-host>
```

- [ ] **Expected:** the play completes with `changed=0` for firmware/RAID, an
      audit `baseline-hosts.start` / `dell_host_baseline.complete` /
      `baseline-hosts.end` sequence, and a **firmware drift report** listing
      every component's discovered version against the (currently empty)
      pinned `target_version`.
- [ ] Cross-check the discovered versions independently on the device:
      ```bash
      # iDRAC UI, or from the host OS if OpenManage is installed:
      omreport chassis bios
      ```
- [ ] Record the observed BIOS / iDRAC / LifecycleController / PERC / NIC
      versions into the §1 placeholders.

> With `target_version` empty in lab `group_vars`, every component reports as
> drifted. That is expected and **safe**: `dell_host_baseline_apply_firmware`
> and `dell_host_baseline_hardware_validated` are `false`, so the role only
> reports — it never submits an update.

### 3.4 PERC / storage inventory (read-only)

- [ ] Discover the **real** controller and drive IDs (the inventory IDs are
      format placeholders today):
      ```bash
      # read-only view via the collection the role already uses:
      #   dellemc.openmanage.idrac_storage_volume  state=view
      # or from the host OS:
      omreport storage controller
      omreport storage vdisk
      omreport storage pdisk
      ```
- [ ] **Expected:** the PERC controller reports as `RAID.Slot.*`; each physical
      disk shows a stable ID of the form
      `Disk.Bay.N:Enclosure.Internal.0-1:RAID.Slot.X-1`; existing virtual disks
      (if any) report their level and state.
- [ ] Record: PERC model + firmware, every physical disk ID, current vdisk
      layout, and whether each disk is **occupied** (holds data) or empty.
- [ ] Do **not** create, delete, or modify any virtual disk. Storage stays
      verify-only.

---

## 4. Expected overall observations

- The read-only run makes **no** mutating iDRAC call and **no** reboot.
- PLAY RECAP shows `unreachable=0 failed=0` for the single limited host.
- Audit events are valid JSONL (one object per line) at `custos_audit_log_path`.
- Firmware drift may be non-zero (lab baselines are empty) — this is a report,
  not an action.
- Storage verification reports the discovered layout; it does not change it.

## 5. Stop conditions (abort and escalate — do not retry, do not fix forward)

| # | Condition | Immediate action |
| --- | --- | --- |
| R1 | Console path (§3.1) is not independent of the management network, or fails. | Abort. There is no recovery path without an independent console. |
| R2 | iDRAC TLS handshake fails against the trusted anchor, or only succeeds with verification disabled. | Abort. Do not set `validate_certs=false`. Investigate the certificate. |
| R3 | Any step would require an apply gate (`apply`, `apply_firmware`, `apply_storage`, `allow_reboot`) to proceed. | Abort. Those are out of scope for this handoff (§7). |
| R4 | The run reports `unreachable>=1` or attempts a connection to a host other than the limited spare. | Abort. Re-check `--limit` and inventory. |
| R5 | A credential appears in any log, diff, or console output. | Abort. Rotate the credential. Open a security incident. |
| R6 | The device model, PERC, or iDRAC generation differs from what the change plan recorded. | Abort. Re-scope; the recovery assumptions may not hold. |

Escalation path: `@custos-arcae/hardware-owners` channel, then
`@custos-arcae/security-reviewers` for R2/R5. See `commission-dell-host.md` §8.3.

## 6. Restricted evidence

Store every captured artifact in the restricted evidence store named in §1
(`TODO(platform-leads): <evidence-store-path-or-URL>`), **not** in Git. The
repository `.gitignore` already excludes `evidence/`, `docs/change-plans/evidence/`,
`*.evidence`, `Catalog.xml`, `*.cab`, and `ansible/.ansible/` (logs). Evidence
may contain service tags and device serials, so it stays in the restricted store
under the change plan (§10.3 of the plan). Name files
`<test-id>/<step>-<slug>.{txt,png}`.

---

## 7. Later lab tests — require SEPARATE authorization

Each of the following is **out of scope for this read-only handoff** and must
not be attempted until its own change plan is approved and the relevant gate is
enabled with lab evidence. The corresponding code paths stay disabled
(`dell_host_baseline_hardware_validated=false`, `apply_firmware=false`,
`apply_storage=false`, `allow_reboot=false`) until then.

| Later test | Gate(s) to enable | Pre-authorization evidence required |
| --- | --- | --- |
| **Firmware activation** (apply + reboot) | `hardware_validated`, `apply`, `apply_firmware`, `allow_reboot` | Approved catalogue (`verify_firmware_catalogue.py` verdict `ok`), HTTPS share or attested non-HTTPS share (`firmware_source_verified`), pinned `target_version` per component, cached vendor recovery per component, SCP export, booked window. |
| **Occupied-disk rejection** (prove a non-empty disk is never claimed) | `hardware_validated`, `apply`, `apply_storage` (test harness only) | Real drive IDs from §3.4, a deliberately occupied disk in the layout, proof the role refuses to claim it. |
| **RAID recovery** (PERC rollback / rebuild path) | `hardware_validated`, `apply`, `apply_storage`, `storage_disks_confirmed_empty` | Exercised PERC recovery procedure on the exact controller model, rollback owner present, backup verified. |
| **Rollback** (SCP re-import + firmware downgrade) | as above, per component | Pre-change SCP export, vendor-supported downgrade confirmed for each component (some BIOS/LC versions do not support downgrade → forward repair/RMA). |

Do not enable any of these gates in this handoff. Enabling them is a separate,
approved change with its own evidence review.

---

## 8. Revision history

| Date | Revision | Author (role) | Notes |
| --- | --- | --- | --- |
| 2026-11-24 | 1.0 | `platform-leads` | Initial operator handoff for the read-only PowerEdge lab test. |
