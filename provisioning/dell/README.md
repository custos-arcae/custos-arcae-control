# Provisioning: Dell PowerEdge

Procedures for taking a **new** Dell PowerEdge server from the shipping pallet
to a state where `custos-arcae-control` can manage it. Everything in this
directory is a *precondition* for the Ansible roles; nothing here is applied
by Ansible.

The operator procedure that ties this together is
[`docs/runbooks/commission-dell-host.md`](../../docs/runbooks/commission-dell-host.md).

## Scope

| Concern | Owned here | Owned elsewhere |
| --- | --- | --- |
| Firmware baseline definition | ✓ (`firmware-baseline.md` when written) | — |
| iDRAC initial configuration | ✓ | `ansible/roles/dell_host_baseline/` applies the ongoing baseline |
| Console / out-of-band access | ✓ | `inventories/` records the address |
| Disk preparation and RAID layout | ✓ | `ansible/roles/dell_host_baseline/tasks/storage.yml` verifies/applies |
| Proxmox VE installation inputs | ✗ | `provisioning/proxmox-ve/` (not yet implemented) |
| Host OS hardening after install | ✗ | `ansible/roles/dell_host_baseline/` and `ansible/roles/proxmox_ve/` |

## Prerequisites

Before a host can be commissioned, the following must be true. Each item is a
stop condition: if it is not satisfied, do not proceed.

1. **Asset registered.** The host has a stable `asset_id` in the asset system
   of record. The same ID is used in inventory, change plans and audit logs.
2. **Physical install complete.** Rack, power (A+B feeds where available),
   cabling, and label per the site's physical standards.
3. **Out-of-band network reachable.** The iDRAC is cabled to the management
   switch and its address is reserved in the site's IPAM. The address is
   reachable from the control node over HTTPS (TCP 443) and SSH (TCP 22).
4. **Console path tested.** Serial-over-LAN or a console server path to the
   host is reachable **independently of the management network**. A firmware
   failure that takes down iDRAC must not also take down the console.
5. **Vendor recovery procedure on hand.** The exact Dell KB article for BIOS
   recovery, iDRAC reset, and PERC firmware rollback for the specific
   PowerEdge model. Printed or cached locally — not behind a vendor login
   that may be unavailable during an incident.
6. **Maintenance window booked.** Firmware and RAID changes require a window.
   The window is named in the change plan.
7. **Change plan filed.** `docs/change-plans/YYYYMMDD-<slug>.md` per
   [`docs/change-plans/template.md`](../../docs/change-plans/template.md).
   Approved by the CODEOWNERS for `provisioning/dell/` and
   `ansible/roles/dell_host_baseline/`.

## Firmware and iDRAC baseline

The baseline itself is defined in
[`ansible/roles/dell_host_baseline/defaults/main.yml`](../../ansible/roles/dell_host_baseline/defaults/main.yml)
under `dell_host_baseline_firmware_targets` and `dell_host_baseline_idrac`.
This directory holds the **provenance** of those values:

- Which Dell catalogue was tested (`Catalog.cab` SHA-256).
- Which PowerEdge models the tested versions apply to.
- The lab evidence (run logs, `omreport` output) that justifies the pin.
- The vendor recovery procedure for each component.

That provenance is recorded in the change plan, not committed here, because
it contains device serial numbers and sometimes vendor case IDs that may
carry personal data of the vendor engineer. The change plan links to the
restricted evidence store.

### Minimum iDRAC settings for a new host

These are applied manually at first boot, before the host is reachable by
Ansible. The `dell_host_baseline` role then enforces them on every run.

| Setting | Value | Why |
| --- | --- | --- |
| iDRAC firmware | Pinned version from the change plan | Reproducibility; recovery path is version-specific. |
| Network | Static, from the site IPAM reservation | DHCP on iDRAC is a lockout risk during a network incident. |
| Default credentials | **Changed immediately.** Root password replaced with a value from the external secret store. | Factory defaults are public. |
| Local users | Only `root` retained, break-glass. All operator access via directory integration. | Attribution (SOC 2 CC6.1). |
| TLS | Minimum 1.2. SSLv3, TLS 1.0, TLS 1.1 disabled. | GDPR Art. 32; ISO 27001 A.10. |
| IPMI over LAN | **Disabled** unless the site change plan explicitly requires it. | IPMI v1.5/v2.0 has a long history of vulnerabilities. |
| Serial-over-LAN | **Enabled.** Baud rate matches the console server. | Break-glass console path. |
| Syslog forwarding | Enabled, target = site SIEM. | ISO 27001 A.12.4 (logging). |
| SNMP | Disabled. Use Redfish. | SNMPv1/v2c community strings are a leak risk. |
| Redfish | Enabled, HTTPS only. | The `dellemc.openmanage` collection uses Redfish for most operations. |
| License | Enterprise or Datacenter license recorded in the asset system. | Some baseline settings (SCP export, thermal profiling) require it. |

### Server Configuration Profile (SCP) export

Before any baseline apply, export the current SCP and store it in the
restricted evidence store named in the change plan. The SCP is the rollback
artefact for iDRAC settings.

```bash
# From the control node, using the pinned dellemc.openmanage 9.7.0 collection.
# The 9.7.0 module uses `command` (not the removed `state`) and
# `scp_components` (not `target`); there is no `share_mnt` option.
# WARNING: ad-hoc module args are visible in the process list and shell
# history. For anything beyond a one-off lab export, wrap this in a playbook
# and resolve the password with lookup('ansible.builtin.env', ...). Never type
# the password inline, and always verify iDRAC TLS with a trusted CA bundle.
ansible localhost -m dellemc.openmanage.idrac_server_config_profile \
  -a "idrac_ip=<iDRAC> idrac_user=${CUSTOS_LAB_IDRAC_USER} \
      idrac_password=${CUSTOS_LAB_IDRAC_PASS} \
      validate_certs=true ca_path=<trusted-ca-bundle> \
      command=export scp_components=ALL export_format=XML \
      share_name=/tmp/scp"
```

The exported XML contains no secrets but does contain the iDRAC network
configuration and user account names. Store it with the same access controls
as the change plan.

## Disk preparation

RAID layout is declared in inventory (`host_vars/<inventory-hostname>.yml`
under `storage.boot` and `storage.data`; file name is the inventory hostname,
per ADR-0003). This directory holds the **rules** for
choosing a layout:

- Boot volume: RAID 1, two disks, minimum 480 GiB each. Survives a single
  disk failure without interrupting the host.
- Data volume: RAID level chosen per workload. RAID 10 for latency-sensitive
  Proxmox VE storage; RAID 6 for capacity-oriented PBS storage. The choice
  is recorded in the change plan with the capacity and failure-domain
  calculation.
- Hot spare: at least one global hot spare per controller in production.
  Lab may omit it.
- Disk model and firmware: pinned in the change plan. Mixed models in a
  single virtual disk are not supported by the PERC firmware and will be
  rejected by the role's drift check.
- **Disks confirmed empty.** The operator attests to this in the change plan
  before any RAID mutation. The role refuses to proceed without the
  attestation flag.

### Non-destructive preparation

For a brand-new host straight from the pallet:

1. Enter the LifecycleController (F10 at POST).
2. Run the hardware inventory. Confirm every expected disk, NIC and PSU is
   present and healthy.
3. Export the inventory as XML. Attach it to the change plan as evidence.
4. Clear any pre-existing RAID configuration **only if** the disks are
   confirmed empty by the receiving process. A returned or reused host may
   carry data from a previous tenant — treat it as untrusted until wiped.
5. Wipe method: PERC "Fast Init" is not sufficient for data sanitisation.
   Use the vendor's secure erase for NVMe/SAS SSDs, or a `blkdiscard` /
   `hdparm --security-erase` pass for SATA. Record the method in the change
   plan. GDPR Art. 32 and ISO 27001 A.8.3 (media sanitisation) both require
   the method to be named, not just the outcome.

## Console access

Two independent paths must exist before commissioning:

1. **iDRAC web console / Redfish virtual console.** Primary path. Requires
   iDRAC to be healthy and reachable.
2. **Serial-over-LAN via the console server.** Fallback path. Must not
   traverse the same switch or the same power feed as the iDRAC network.

The runbook requires the operator to test path 2 **before** starting any
firmware apply. A firmware failure that bricks iDRAC leaves the console
server as the only way to observe the host.

## Credentials

- iDRAC root password: generated per-host, stored in the external secret
  store, never in Git, never in inventory. The inventory holds only the
  **name** of the environment variable (`oob_controller.password_var`).
- Operator iDRAC accounts: per-operator, via directory integration. Shared
  accounts are prohibited (SOC 2 CC6.1 attribution).
- SSH to the host OS: key-based only. The operator's key is added by the
  `dell_host_baseline` role's host-OS section, not by this provisioning step.
- Break-glass: the iDRAC root account and a local SSH key held in the site's
  physical safe. Access is logged and requires two-person authorisation.

## What is NOT done here

- Proxmox VE installation. See `provisioning/proxmox-ve/` (not yet
  implemented).
- Host OS hardening beyond the package set in `dell_host_baseline`. The
  `proxmox_ve` role owns the rest.
- Network switch port configuration. Owned by `ansible/roles/switch_baseline/`
  (not yet implemented) and the site's network runbook.
- Monitoring agent installation. Owned by `ansible/roles/monitoring/` (not
  yet implemented).

## Testing this procedure

The lab inventory (`inventories/lab/hosts.yml`) contains two fictional Dell
hosts with RFC 5737 / RFC 6761 non-routable addresses. On every PR that
touches `ansible/`, `provisioning/`, or `inventories/`, the `validate`
workflow (`.github/workflows/validate.yml`) runs, fully offline:

- `ansible-lint --profile production`;
- `--syntax-check` on every playbook against the lab inventory;
- inventory validation (`ansible-inventory --graph` / `--list`) for the lab
  and offline inventories;
- an **offline fixture run** of `dell_host_baseline`
  (`ansible/tests/offline/`) with `dell_host_baseline_offline=true` and
  `ansible_connection=local`, which exercises the authorization, firmware
  drift, storage-contract, and audit logic with **zero** network calls and no
  privilege escalation;
- secret scanning (gitleaks + detect-secrets) and the change-plan guard, each
  with a fake-fixture self-test.

CI deliberately does **not** run `baseline-hosts.yml` against the lab iDRAC
addresses: the role's read-only info tasks set `check_mode: false`, so a
`--check` run would still attempt real HTTPS to unreachable `198.51.100.x`
hosts. The offline seam exists precisely so CI never needs a device.

None of this validates the manual steps above (LifecycleController, console
path, disk wipe) or the destructive apply path. Those require real hardware:
they are validated once per PowerEdge model, in lab, and the evidence is
attached to the model's change plan.
