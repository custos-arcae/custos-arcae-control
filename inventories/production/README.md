# Production inventory — access restricted

This directory holds the inventory for live Custos ARCAE sites. It is
**intentionally not populated** in the public working tree until a site is
commissioned under a filed change plan.

Layout is **country-first** — `production/<country-code>/<site-id>/` — per
ADR-0003. Site and host naming, the owner-code register and the site register
(short codes such as `lt-vno01`) are defined there; no country or site
directory is created until its site is commissioned.

## Current sites

| Site | Path | Status | Authorising change plan |
| --- | --- | --- | --- |
| `lt-vilnius-01` | `production/lt/lt-vilnius-01/` | Not yet commissioned. Documented placeholder only (ADR-0003); no directory is committed until commissioning. | — |

No production host, switch, IP address, asset ID or credential may appear in
this tree until:

1. A change plan is filed under `docs/change-plans/YYYYMMDD-<slug>.md`.
2. The plan names the executor role, approver role, target devices,
   maintenance window, verification steps, stop conditions and recovery path.
3. CODEOWNERS-required reviewers (`platform-leads`, `security-reviewers`,
   `site-lt-vilnius`) have approved the plan.
4. The out-of-band console path for every target device has been tested
   independently of the management network.

## What may live here once commissioned

```
production/
└── lt/
    └── lt-vilnius-01/
        ├── hosts.yml              # devices, asset IDs, group membership
        ├── group_vars/
        │   ├── all.yml            # site-wide non-secret settings
        │   ├── dell_hosts.yml     # firmware/iDRAC baseline targets
        │   ├── proxmox_nodes.yml  # cluster name, storage, network
        │   ├── pbs_servers.yml    # retention, prune schedules (secret refs only)
        │   ├── management_switches.yml
        │   └── monitoring_endpoints.yml
        └── host_vars/
            └── <inventory-hostname>.yml  # per-device deltas; carries asset_id,
                                          # model, rack, serial as fields (ADR-0003)
```

## What may NEVER live here

- Plaintext passwords, API tokens, private keys, certificates, recovery seeds,
  VPN pre-shared keys, or vault passwords — even "temporarily".
- Ansible Vault files whose vault key owner is not documented in the site
  change plan.
- Natural-person identifiers (names, personal emails, personal phone numbers).
  Ownership is expressed as team/role and resolved via the HR system of record
  (GDPR data-minimisation).
- Vendor support case numbers containing personal data of a named engineer.
  Link the case from the change plan instead.

## CI exposure

`.github/workflows/validate.yml` runs on `pull_request` only and has no access
to production credentials. Any workflow that would need production access must
run on a self-hosted runner inside the site boundary and is out of scope for
this repository — see `docs/adr/` for the decision record when it is written.

## Editing this directory

Edits to `inventories/production/**` require:

- A change plan in the same PR (enforced by the `change-scope` job in
  `.github/workflows/validate.yml`).
- Approval from all three CODEOWNERS teams listed above.
- A signed commit from the executor's role account.

If you are reading this and expected to find live inventory, stop and open an
issue: either the site has not been commissioned yet, or the inventory has
been moved to a restricted repository under an ADR you have not read.
