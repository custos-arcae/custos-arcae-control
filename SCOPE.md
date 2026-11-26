# SCOPE

This document defines the boundaries of `custos-arcae-control`. Reviewers use it
to reject out-of-scope changes early. If a change is not clearly in scope, it
does not belong in this repository.

## In scope

`custos-arcae-control` owns the **declarative, reviewable, reproducible**
description of how a Custos ARCAE site is built and operated:

1. **Host commissioning inputs**
   - Dell firmware and iDRAC baseline definition.
   - Console / out-of-band access assumptions.
   - Disk layout and RAID preparation inputs.
   - Proxmox VE installer answer-file format and pinned installer version.

2. **Inventory of managed entities**
   - Hosts, switches, and out-of-band controllers per environment (`lab`,
     `production/lt/lt-vilnius-01`; country-first layout per ADR-0003).
   - Stable asset IDs and site/device-specific approved settings.
   - **Secret references** (never plaintext credentials).

3. **Reusable configuration logic**
   - Ansible roles that describe *how* a component is configured
     (`dell_host_baseline`, `proxmox_ve`, `proxmox_backup`,
     `management_network`, `switch_baseline`, `monitoring`).

4. **Operator entry points**
   - One Ansible playbook per change class, each with a bounded target set:
     host baseline, Proxmox VE, Proxmox Backup, management network, switches,
     monitoring, and a strictly read-only `verify-site.yml`.

5. **Governance artefacts**
   - CODEOWNERS and required reviewers per path.
   - PR template, automated validation (YAML/Ansible lint, secret scan, safe
     lab checks).
   - Architecture Decision Records, change-plan template, and runbooks that
     specify prerequisites, authorised executors, success criteria, stop
     conditions, and recovery.

## Out of scope

The following do **not** belong here. Proposals touching them should be
redirected to the owning system.

- **Runtime workloads.** VM/CT definitions, guest OS images, application
  configuration, Kubernetes manifests.
- **Secrets themselves.** Passwords, API tokens, private keys, certificates,
  recovery seeds. These live in Ansible Vault / the external secret store,
  referenced from inventory by name only.
- **Personal data.** Operator names, personal emails, personal phone numbers,
  HR data. Ownership is expressed as team/role and resolved externally
  (GDPR data-minimisation).
- **Vendor tickets and support case management.** Use the vendor portal; link
  the case ID from the change plan.
- **Physical site documentation** (rack elevations, cabling diagrams, power
  single-lines) unless they are required as verification evidence for a
  runbook and stored as text/drawings under `docs/`.
- **Application-level monitoring rules** for services that are not part of the
  infrastructure estate.
- **Ad-hoc scripts.** Anything executed once and never reviewed is a shadow
  change; it must be either promoted to a role/playbook or discarded.
- **Production credential material in CI.** No production secret, key or
  certificate may be reachable from a pull-request workflow.

## Environment boundaries

| Environment | Purpose | CI may touch? | Change plan required? |
| --- | --- | --- | --- |
| `lab` | Disposable validation of roles, playbooks, and answer-file formats. | Yes (safe, read-mostly checks). | No, but PR description must state lab evidence. |
| `production/lt/lt-vilnius-01` | The live Vilnius site (country-first path, ADR-0003). | **No.** Production credentials are never available to PR CI. | **Yes**, filed under `docs/change-plans/`. |

Adding a new production site requires an ADR under `docs/adr/` describing:
network reachability, secret-store binding, escalation path, and the delta
from the reference site `lt-vilnius-01` (inventory path
`production/lt/lt-vilnius-01`).

## Acceptance criteria for scope disputes

A change is in scope only if **all** of the following hold:

1. It is declarative and reviewable in a PR diff.
2. It has a named executor role in a runbook (or introduces one).
3. Its verification and recovery are describable in text.
4. It contains no secret material and no personal data.
5. It does not duplicate a system of record that already owns the concern.

If any item fails, close the PR and route the change to the correct system.
