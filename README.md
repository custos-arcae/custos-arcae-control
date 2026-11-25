# custos-arcae-control

Infrastructure-as-Code control plane for the Custos ARCAE estate: Dell hosts,
Proxmox VE, Proxmox Backup Server (PBS), management networking, switches and
monitoring.

This repository is the **system of record** for how a site is built and how it
is changed. It is operated under a SOC 2 / ISO 27001 / GDPR control set: every
change is reviewed, attributable, reproducible and reversible.

> Read [SCOPE.md](SCOPE.md) before proposing a change and [AGENTS.md](AGENTS.md)
> before reviewing one. The first commissioned workflow is the Dell host
> baseline — see [`docs/runbooks/commission-dell-host.md`](docs/runbooks/commission-dell-host.md).

---

## Repository layout

```
custos-arcae-control/
├── README.md               ← you are here
├── SCOPE.md                ← what this repo owns and does not own
├── AGENTS.md               ← review rules, required evidence, hard stops
├── CHANGELOG.md            ← operator-visible change history
├── .github/
│   ├── CODEOWNERS          ← required reviewers per path (production is gated)
│   ├── pull_request_template.md
│   └── workflows/
│       └── validate.yml    ← YAML/lint/secret-scan/lab-safe checks
├── inventories/
│   ├── lab/                ← disposable, safe to run from CI
│   └── production/
│       └── lt-vilnius-01/  ← restricted; secret refs only, no plaintext creds
├── provisioning/
│   ├── dell/               ← iDRAC / firmware / disk / OS-install inputs
│   └── proxmox-ve/         ← installer answer file + notes
├── ansible/
│   ├── ansible.cfg
│   ├── requirements.yml    ← pinned collections & roles
│   ├── playbooks/          ← operator entry points, one per change class
│   └── roles/              ← reusable configuration, values come from inventory
└── docs/
    ├── adr/                ← architecture decision records
    ├── change-plans/       ← per-change plan (template.md is the seed)
    └── runbooks/           ← operator procedures: who, when, verify, stop, recover
```

Only files whose workflow is actually implemented should exist. Empty stubs are
a compliance smell — do not add them speculatively.

---

## What belongs where

| Location | Owns |
| --- | --- |
| `provisioning/` | Getting a **new** device ready to be managed: Dell firmware/iDRAC baseline, console access, disk preparation, Proxmox install inputs. Answer-file formats are tested against the pinned installer version. **Credentials are injected at execution time, never committed.** |
| `inventories/` | Which hosts and switches each environment manages, their stable asset IDs, and approved site/device-specific settings. Production inventory is access-restricted. Credentials live behind secret references (Ansible Vault / external secret store). |
| `ansible/roles/` | **How** a component is configured. Roles are reusable and site-agnostic. Example: the switch role defines how to apply an approved port configuration. |
| `ansible/playbooks/` | **Operator entry points**, one per change class (host / network / backup / monitoring / verify). Bounded target sets, reviewable in isolation. `verify-site.yml` is strictly read-only. |
| `.github/` | Required reviewers, PR prompts, automated checks: YAML validation, Ansible lint, secret scanning, safe lab checks. **Production credentials are never present in PR CI.** |
| `docs/` | ADRs, change plans, runbooks. A runbook identifies prerequisites, authorised executors, success criteria, stop conditions and recovery. |

---

## Verification and recovery by change type

| Change | Verify after applying | Prepare before applying |
| --- | --- | --- |
| Dell firmware / iDRAC | Host boots, console access works, hardware health acceptable, interfaces and storage visible. | Vendor-supported recovery and downgrade options for the exact update. Maintenance window scheduled. Console path identified and tested. |
| Proxmox VE host / cluster | Cluster quorum, storage, networking, representative guests healthy. | Remaining capacity confirmed. Evacuation or shutdown plan for workloads. Node recovery procedure agreed — some changes require rebuild or forward repair. |
| Management network / switch | Management path, out-of-band console, required connectivity, redundancy paths all work. | Known-good configuration saved to restricted storage. Independent console access tested. Automatic configuration reversion enabled where supported. |
| PBS policy / configuration | Representative backup completes and a restore produces usable data. | Current policy preserved. Pause/rollback documented. Retention or pruning changes require specific review — deleted backups may be unrecoverable. |
| Monitoring configuration | Expected alert reaches the responsible operator and clears after recovery. | Prior rules and routing available. Restore path tested. |

---

## Local development

The repository contains a small Python helper package (`src/custos_arcae_control/`)
used by tooling and tests. Infrastructure work does not require it, but the
checks in CI do.

```bash
# Python 3.12+
sudo apt install python3 python3-venv python3-pip git

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Lint / format / types / tests
ruff check src/ tests/
ruff format src/ tests/
mypy src/
pytest
```

Ansible tooling is installed from `ansible/requirements.yml`:

```bash
ansible-galaxy install -r ansible/requirements.yml
```

---

## Running a change

1. Read [`SCOPE.md`](SCOPE.md) — confirm the change belongs in this repository.
2. Copy [`docs/change-plans/template.md`](docs/change-plans/template.md) into
   `docs/change-plans/YYYYMMDD-<slug>.md` and fill it in.
3. Open a PR. CODEOWNERS will require the reviewers for the affected paths.
4. Follow the runbook under [`docs/runbooks/`](docs/runbooks/) for the target
   change class. Do not improvise.
5. After applying, capture the verification evidence listed in the runbook and
   link it from the change plan.

---

## Security and privacy posture

- **No secrets in Git.** Ansible Vault, environment variables or an external
  secret store. CI runs `gitleaks` and `detect-secrets` on every PR.
- **Least privilege.** Operator accounts are non-root with sudo scoped to the
  commands a role needs. iDRAC/IPMI/switch accounts are per-operator, never
  shared.
- **GDPR.** Inventory stores asset IDs, hostnames, roles and network facts.
  It does **not** store natural-person identifiers (operator names, personal
  emails, personal phone numbers). Ownership is expressed by team/role and
  resolved via the HR/asset system of record.
- **Attribution.** Signed commits and signed tags are strongly recommended.
  Merges are squash-only so a single reviewable change equals a single commit.
- **Reversibility.** Every runbook has a stop condition and a recovery path.
  If you cannot articulate both, the change is not ready.

See [`AGENTS.md`](AGENTS.md) for the review contract.
