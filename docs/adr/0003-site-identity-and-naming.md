# ADR-0003: Site identity, host naming, and inventory directory convention

| | |
| --- | --- |
| Status | Proposed |
| Date | 2026-11-26 |
| Deciders | `@custos-arcae/platform-leads`, `@custos-arcae/security-reviewers` (teams, not individuals — GDPR Art. 5(1)(c)) |
| Applies to | `custos-arcae-control` inventory layout; naming convention for all `custos-arcae` sites and spokes |
| Related | ADR-0002 (multi-project autonomous control-plane architecture) |
| Supersedes | — |

## Context

`custos-arcae-control` today carries a single, uncommissioned placeholder site
directory `inventories/production/lt-vilnius-01/`. ADR-0002 plans expansion to
Latvia, Estonia, Poland and eventually the EU-27, with per-project workloads
for ViaVitae, Journey of Life and JolArca Marketplace.

There is no agreed rule for naming sites, hosts, clusters, VMs and switches,
nor for where hardware identity (model, asset ID, rack, serial) lives.
Without one:

1. Names get assigned ad hoc and become immutable liabilities — a Proxmox VE
   cluster name cannot be changed after `pvecm create` without destroying the
   cluster.
2. Hardware replacement would force host renames, breaking DNS, monitoring
   series, backup namespaces and certificate identities.
3. A flat `production/<site-id>/` layout does not group the planned ~27
   countries and mixes unrelated tenants in one directory.

Live Journey of Life assets (`pve-prod-hv01`, `prox01`, `pbs01`,
`llm-prod-lt01`, `mcp-prod-lt01`, `rag-prod-lt01`, `her-prod-lt01`, and their
VMIDs) are owned by a different system of record —
`journeyoflife-org/jol-infrastructure` (`docs/servers/*.md`,
`inventory/prod/`). This ADR does not duplicate, move or rename them.

This ADR authorises **no** site commissioning, **no** hardware purchase and
**no** rename of a running asset. Adding a production site still requires its
own ADR and change plan per `SCOPE.md` (§ Environment boundaries).

## Decision

### 1. Naming grammar

```text
Site ID        <country>-<city>-<site-number>                 lt-vilnius-01
Short site     <country>-<iata-city-code><site-number>        lt-vno01
Physical host  <site-id>-<owner>[-<purpose>]-<role><NN>       lt-vilnius-01-jol-pve02
Cluster        <short-site>-<owner>-<role><NN>                lt-vno01-jol-pve01
VM / LXC       <site-id>-<owner>-<env>-<service><NN>          lt-vilnius-01-jol-prod-rag01
Switch         <site-id>-<network-role><NN>                   lt-vilnius-01-tor01
```

- `<country>` — ISO 3166-1 alpha-2, lowercase.
- `<owner>` — project/organisation code from the register in §2.
- `<purpose>` — optional, from a closed list: `svc` (shared project-service
  host), `mgmt` (Custos Arcae management-plane host).
- `<role>` — physical hosts: `pve` (Proxmox VE node), `pbs` (Proxmox Backup
  Server); standalone bare-metal application hosts use an application token in
  the role position (e.g. `llm`, `bitrix` — see Open implementation items).
- `<network-role>` — `tor` (top-of-rack), `oob-sw` (out-of-band management).
- `<env>` — `prod`, `stage` or `lab`; workload names carry it, physical hosts
  omit it (environment is implied by the inventory they live in).
- `<NN>` — zero-padded two digits for small named groups; a wider sequence or
  the Proxmox VMID for large VM/LXC fleets. VMID remains the numeric system of
  record; the instance number is a human label mapped to it in the spoke's
  inventory.
- VM names deliberately omit the physical host number, so moving a guest
  within the site's cluster keeps its name.

Example: `lt-vilnius-01-jol-pve02` is Journey of Life's second Proxmox VE
node at Vilnius site 01; `lt-vilnius-01-jol-prod-rag01` is its first
production RAG VM at that site.

### 2. Owner code register

| Code | Owner |
| --- | --- |
| `vv` | ViaVitae |
| `jol` | Journey of Life |
| `ja` | JolArca Marketplace (matches the `ja-*` service names in ADR-0002 §4) |
| `ca` | Custos Arcae (central infrastructure / management plane) |

### 3. Hardware identity is inventory data, never part of the name

Model, `asset_id`, rack location, serial number and management endpoint are
stored as fields of the host in `host_vars/<inventory_hostname>.yml`, so a
failed server can be replaced without changing the naming convention or
breaking references. `asset_id` remains the stable identity required by
AGENTS.md §4. Values are only populated when real; unknown values are marked
`TODO(<owner-role>)` and block commissioning (AGENTS.md §1.5 — never invent
asset IDs, serials or addresses). Note that Ansible auto-loads
`host_vars/<inventory_hostname>.yml`; the file name must equal the inventory
hostname, not the asset ID.

### 4. Site register

| Country | Site ID | Short site code | Status |
| --- | --- | --- | --- |
| Lithuania | `lt-vilnius-01` | `lt-vno01` | Placeholder directory exists; not yet commissioned |
| Latvia | `lv-riga-01` | `lv-rix01` | Proposed only — no directory, no site ADR yet |
| Estonia | `ee-tallinn-01` | `ee-tll01` | Proposed only — no directory, no site ADR yet |
| Poland | `pl-warsaw-01` | `pl-waw01` | Proposed only — no directory, no site ADR yet |

Short site codes are assigned **only** in this register. A second site in the
same city increments the site number (`lv-riga-02` / `lv-rix02`). A site's
purpose (recovery location, regional deployment, second production) is decided
in that site's own ADR, not here.

### 5. Country-first inventory directory convention

```text
inventories/production/
├── README.md
└── <country-code>/<site-id>/          ← canonical pattern
    ├── hosts.yml
    ├── group_vars/
    └── host_vars/
```

Lithuania's documented path is `inventories/production/lt/lt-vilnius-01/`.
The country level keeps each tenant's sites grouped for CODEOWNERS scoping and
scales to EU-27 without reorganisation.

Rules:

- A country or site directory is created **only** when that site is
  commissioned under a filed change plan; this ADR creates no empty
  directories (AGENTS.md §2 — no speculative stubs).
- The change-plan guard and CI production trigger match the prefix
  `inventories/production/`, so they cover every future country directory
  without edits.
- Each additional site adds its own CODEOWNERS rule
  (`/inventories/production/<cc>/<site-id>/  @custos-arcae/platform-leads
  @custos-arcae/security-reviewers @custos-arcae/site-<city>`) naming a
  site-owner team, alongside the catch-all production rule.

### 6. Relationship to existing Journey of Life names

The live Journey of Life hostnames and VMIDs **stay unchanged**. `custos-
arcae-control` does not record or rename them; `jol-infrastructure` remains
the system of record. When the `custos-arcae-control-journey-of-life` spoke
exists (ADR-0002 §1), a migration register (current hostname, proposed
hostname, asset ID, owner, site, VMID, DNS/backup/monitoring/certificate
dependencies) lives there, and no rename happens except under an approved
change plan owned by that project. This convention applies to **new**
deployments from the point it is accepted.

## Consequences

### Positive

- One predictable name reveals site, owner and role for every asset; DNS,
  monitoring labels and backup namespaces can be derived mechanically.
- Hardware can be replaced without renames (identity lives in fields).
- The inventory tree scales to EU-27 without restructuring.
- Existing assets and repositories are untouched by adoption of the
  convention.

### Negative

- Hostnames are long (e.g. `lt-vilnius-01-jol-prod-hermes01`, 31 chars —
  within the 63-char DNS label limit, but operators must not truncate them
  inconsistently).
- The register discipline is manual until a CI check validates names against
  the grammar; an unregistered short code would defeat the scheme. Mitigation:
  short codes are assigned only in §4, and CODEOWNERS gates every edit.

### Neutral

- No production site is created or authorised by this ADR.
- The placeholder `lt-vilnius-01` directory is uncommissioned and empty, so
  documenting the nested path changes references only — no inventory move is
  required at this time.

## Alternatives considered

| Approach | Rejection rationale |
| --- | --- |
| Flat `production/<site-id>/` (status quo) | ~27 countries ×N sites mix in one directory; no country-level CODEOWNERS scoping. |
| Encode model/serial/rack in hostnames | Hardware failure would force renames; breaks DNS, monitoring history, backup namespaces and certs. |
| Rename live JoL assets to the new convention now | Couples a naming decision to production changes in another project's estate; renames need per-asset change plans. |
| Create `lv/`, `ee/`, `pl/` directories up front | Speculative empty directories are prohibited (AGENTS.md §2) and would fake site existence. |

## Compliance mapping

| Control | How this decision satisfies it |
| --- | --- |
| SOC 2 CC8.1 (change management) | Naming/site-identity changes are gated on this ADR; each site still needs its own change plan. |
| ISO 27001 A.5.9 / A.8.32 (inventory of assets, change management) | Every asset name resolves to owner + site + role; hardware inventory fields carry asset ID and location. |
| GDPR Art. 5(1)(c) (data minimisation) | Owner codes are project/team identifiers, never natural persons. |

## Open implementation items (owner decision required before acceptance)

| # | Item | Blocks |
| --- | --- | --- |
| 1 | **Bitrix host**: self-hosted or cloud (ADR-0002 open question 1). Only a self-hosted decision creates an `lt-vilnius-01-<owner>-bitrixNN` host, and the owner code must be chosen (`ca` vs the consuming project). | Bitrix naming |
| 2 | **Cluster layout**: pilot on one shared cluster with SDN isolation, or dedicated `<short-site>-<owner>-pve01` clusters per project from day one; confirm the Proxmox cluster-name length/character limit against the pinned PVE release before first `pvecm create`. | Cluster naming |
| 3 | **Host-placement risk**: the shared project-service host (`lt-vilnius-01-ca-svc-pve01`) puts Art. 9 (JoL) and PCI-scoped (JolArca) VMs in one physical failure domain; decide anti-affinity rules or accept the pilot risk in the site change plan. | Service VM placement |
| 4 | **Site-owner teams**: `site-lt-vilnius` and per-country team slugs do not exist yet in the GitHub org; CODEOWNERS lines for site paths are inert until an administrator creates them with write access (AGENTS.md §5.1). | Per-site CODEOWNERS |

## Review

Next review due: **2027-11-26** (or upon acceptance of ADR-0002, whichever is
earlier). At review, confirm:

- The owner-code and site registers are current and no ad-hoc names were
  assigned outside §2/§4.
- Grammar tokens (`purpose`, `role`, `network-role`) are still a closed list.
- The first commissioned site validated the convention in practice.
- Open implementation items 1–4 are resolved or explicitly deferred.
