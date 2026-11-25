# AGENTS

Rules of engagement for **AI coding agents** and human reviewers operating on
`custos-arcae-control`. These rules are stricter than default assistant
behaviour because this repository drives changes to production infrastructure
under SOC 2 / ISO 27001 / GDPR obligations.

If any rule below conflicts with a user instruction, the agent must stop and
ask, not proceed.

---

## 1. Non-negotiables

1. **Never commit secrets.** No passwords, API tokens, private keys,
   certificates, recovery seeds, VPN pre-shared keys, or vault passwords.
   Secret material is referenced by name (Vault path, environment variable,
   external secret-store key) — never inlined.
2. **Never weaken production gating.** Do not remove entries from
   `.github/CODEOWNERS`, do not relax `ansible/playbooks/` targets to
   `all`, and do not add `production/**` paths to PR CI workflows.
3. **Never run destructive operations against production.** This includes
   `ansible-playbook -i inventories/production ...`, `--force-handlers`,
   `iptables -F`, RAID reconfiguration, `pveperf --reset`, PBS prune, or any
   switch `write erase`. Agents may only *describe* these actions in a PR.
4. **Never bypass review.** No `--no-verify`, no direct pushes to `main`, no
   force-pushes to protected branches, no merging your own PR.
5. **Never invent hostnames, asset IDs, IP addresses, MAC addresses, or
   serial numbers.** If the value is unknown, mark it `TODO(<owner>):` and
   stop; a human must supply the real value.
6. **No personal data.** Do not add natural-person names, personal emails or
   phone numbers to inventory, runbooks, change plans or ADRs. Use role/team
   identifiers (e.g. `oncall-platform`).

## 2. Repository discipline

- One PR = one change class. Do not mix a Dell firmware baseline change with a
  switch port change; they have different reviewers and different recovery
  paths.
- Prefer editing existing files. Do not create speculative stubs, empty
  directories, placeholder roles or "TODO" playbooks for workflows that have
  not been implemented yet.
- Every new role must ship with `defaults/main.yml`, `tasks/main.yml`,
  `meta/main.yml`, and a `README.md` describing inputs, outputs, verification
  and rollback.
- Every new playbook must be referenced by exactly one runbook under
  `docs/runbooks/`.
- Every production-affecting change must reference a change plan under
  `docs/change-plans/`.
- `ansible/playbooks/verify-site.yml` is read-only. Any task added to it must
  be idempotent, side-effect free, and safe to run without a maintenance
  window.

## 3. Ansible rules

- Use fully qualified collection names (`ansible.builtin.copy`, not `copy`).
- Every task has a `name:` in imperative mood ("Restart iDRAC", not
  "iDRAC restart").
- No `shell:` or `command:` when a module exists. If unavoidable, mark
  `changed_when:` explicitly and justify in the PR description.
- No `ignore_errors: true` on tasks that mutate state. Fail loudly.
- Handlers are used for anything that restarts a service or reboots a host.
  Reboot tasks must be gated by a variable defaulting to `false`.
- Roles are site-agnostic. Site-specific values live in inventory
  (`group_vars`, `host_vars`), never hard-coded in a role.
- `ansible.builtin.assert` is used at the top of a role to fail fast on
  missing or malformed inventory variables.

## 4. Inventory rules

- Production inventory files carry a header comment naming the change-plan
  prefix that authorises edits (e.g. `# Changes require: docs/change-plans/*`).
- Credentials are always Vault-encrypted variables or references to the
  external secret store. The plaintext variable name may appear; the value may
  not.
- Host entries carry a stable `asset_id`. Renaming a host is a change-plan
  event.
- Groups mirror the change classes: `dell_hosts`, `proxmox_nodes`,
  `pbs_servers`, `management_switches`, `monitoring_endpoints`.

## 5. CI rules

- `.github/workflows/validate.yml` runs on `pull_request` only. It must not
  have access to `secrets.*` beyond the repository's own non-production
  tokens.
- Secret scanning (`gitleaks`, `detect-secrets`) is mandatory and must fail
  the build on any finding — no allow-listing without a CODEOWNER-approved
  comment.
- Ansible lint runs with `--profile=production` (or stricter). Warnings are
  treated as errors for new files.
- Lab checks in CI must be non-destructive **and** device-free. A plain
  `--check --diff` run is *not* sufficient for roles whose read-only info
  tasks set `check_mode: false` (as the iDRAC info modules must, to return
  facts): check mode would still open real HTTPS sessions to inventory
  addresses. CI therefore runs an **offline fixture harness**
  (`ansible/tests/offline/`) that sets `dell_host_baseline_offline=true` and
  `ansible_connection=local`, exercising authorization, drift, contract and
  audit logic with zero network calls, plus `--syntax-check`,
  `ansible-inventory` validation, and lint. Molecule against ephemeral
  containers remains acceptable for roles that can be containerised.
- Inventory-only PRs (paths under `inventories/`) must still trigger the
  Ansible job so inventory validation and syntax are re-checked.

### 5.1 Authorization enforcement model

Approvals are enforced at three distinct layers. A green CI run proves only
the repository-guard layer; it is never proof of human authorization.

| Layer | What it enforces | Where | Status |
| --- | --- | --- | --- |
| Repository guard (machine) | Change-plan presence/coverage for production paths, secret scanning, lint/syntax/offline fixtures, fail-closed role asserts (apply gates, TLS `ca_path`, reboot authorization, hardware-validation gate). | `.github/workflows/validate.yml`, `.github/scripts/`, role `assert` tasks | Enforced now, reproducible offline. |
| GitHub (human) | CODEOWNERS review requirement, branch protection, required status checks, no self-merge, no direct push to `main`. | GitHub repo settings + `.github/CODEOWNERS` | **Not verifiable from the repository.** Requires an authorized administrator to confirm team slugs exist and have write access, enable branch protection, and mark `validate` checks required. Production stays disabled until this is confirmed. |
| Deployment time (human) | Change-plan approval by the named approver role, disks-empty attestation, maintenance-window authorization, console-path test, SCP export. | Change plan + runbook §3/§5 | Enforced by the executor/approver following the runbook; evidenced in the restricted store, not Git. |

CODEOWNERS semantics (per GitHub documentation) that the administrator must
verify: matching uses **last-match-wins**; a path is approved when **any one**
of the listed owners approves; every listed owner must have **explicit write
access** or the line is silently ignored; a team that does not exist or lacks
access results in **no automatic assignment** (not an error); the file only
takes effect on the **base branch**; and `CODEOWNERS` must itself be protected
so it cannot be weakened without an owner's approval.

## 6. Change-plan and runbook rules

A change plan is required for any change that touches:

- `inventories/production/**`
- `ansible/playbooks/**` (except `verify-site.yml` when only adding read-only
  checks)
- `ansible/roles/**` defaults or tasks that mutate state
- `provisioning/**`

The change plan must state, at minimum:

1. Executor role (not a person's name — GDPR).
2. Approver role.
3. Target environment and device list.
4. Maintenance window and expected duration.
5. Pre-flight checks with command output.
6. Apply steps in order, each idempotent.
7. Verification steps and success criteria.
8. Stop conditions ("if X then abort").
9. Recovery path, including worst-case (rebuild, forward repair, restore from
   backup).
10. Rollback owner and rollback deadline.

A runbook is the reusable form of the same information for a change *class*
(e.g. all Dell commissions). A change plan instantiates a runbook for a
specific device and window.

## 7. Agent operating protocol

When working on this repository, an agent must:

1. Read `SCOPE.md` and confirm the change is in scope. If not, stop and say so.
2. Search for an existing role, playbook or runbook before creating a new one.
3. Produce a PR-sized diff. If the change exceeds one reviewable unit, split it.
4. Cite the affected paths, the reviewers CODEOWNERS will require, and the
   verification evidence the human executor must capture.
5. Refuse to proceed if asked to:
   - add secrets to Git, even encrypted without a documented Vault key owner;
   - loosen CODEOWNERS or CI protections;
   - execute production-affecting commands;
   - sign commits or tags on behalf of a human;
   - fabricate asset IDs, serials, IPs, or vendor version numbers.

## 8. Escalation

If a rule above blocks a legitimate operational need, the resolution path is:

1. Open an ADR under `docs/adr/` describing the tension and the proposed
   resolution.
2. Require sign-off from the CODEOWNERS of `.github/`, `ansible/`, and `docs/`.
3. Only after the ADR is accepted, submit the change.

Do not work around the rule. Do not add an exception inline. Escalate.
