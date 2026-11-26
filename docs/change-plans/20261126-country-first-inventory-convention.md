# Change plan: Country-first inventory convention and site/host naming (ADR-0003)

> Instantiates [`template.md`](template.md). Enforced by
> [`AGENTS.md`](../../AGENTS.md) §6. This plan **authorises no site
> commissioning, no hardware purchase, and no change to any running asset**. It
> is a Git/GitHub-only governance change that adds a naming/layout convention
> (ADR-0003) and a documented, uncommissioned production placeholder README.
>
> It appears under `docs/change-plans/` because it edits paths under
> `inventories/production/**` (`README.md`) and `provisioning/dell/` — both of
> which trip the repository change-plan guard
> (`.github/scripts/check_change_plan.py`). No live device is touched.

## 0. Identification

| Field | Value |
| --- | --- |
| Change plan ID | `20261126-country-first-inventory-convention` |
| Title | Adopt country-first inventory layout and site/host naming convention |
| Change class | host-baseline (declared to satisfy the guard's class match for the touched `provisioning/dell/` path; scope is documentation/convention only — no host is baselined by this plan) |
| Environment | Documentation/convention change. Touches the `inventories/production/` **placeholder path** and lab docs; **no live device, cluster or switch is in scope**. |
| Runbook | `docs/runbooks/commission-dell-host.md` — a future *consumer* of this convention; not executed by this plan. |
| ADR | `docs/adr/0003-site-identity-and-naming.md` (status: Proposed) |
| PR | `TODO(<executor-role>): link once the branch is opened` |
| Filed | 2026-11-26 |
| Status | Draft |

## 1. Roles

> GDPR Art. 5(1)(c): **roles/teams only**, never natural persons. Individual
> attribution lives in Git signatures and PR reviews.

| Role | Team / handle |
| --- | --- |
| Executor | `@custos-arcae/platform-leads` |
| Approver | `TODO(<owner-role>): a non-author approver` — see §9 approval-independence gap |
| Rollback owner | `@custos-arcae/platform-leads` |
| On-call during window | Not applicable — no execution against any system (§4) |
| Vendor support contact *(optional)* | Not applicable |

## 2. Objective

Establish a single, reviewable naming and inventory-layout convention before any
Custos Arcae production site is commissioned, so that site/host/cluster/VM
identities are derived mechanically and remain stable across hardware
replacement. Implements ADR-0003: the naming grammar (§1), owner-code register
(§2), the rule that hardware identity lives in `host_vars` fields rather than in
names (§3), the site register (§4), and the country-first directory convention
`inventories/production/<country-code>/<site-id>/` (§5). This PR records the
convention and an intentionally uncommissioned production README; it creates no
site and no device record.

## 3. Scope

### 3.1 Target devices

**None.** No asset is contacted, renamed, created or configured. The table is
present to satisfy the template; it is deliberately empty.

| Asset ID | Hostname | Role in change | Notes |
| --- | --- | --- | --- |
| — none — | — none — | documentation only | No `asset_id:` value is introduced into `inventories/production/**` by this PR (verified below), so the guard requires no asset coverage. |

### 3.2 Explicitly out of scope

- Commissioning `lt-vilnius-01` or any other site — requires its **own** ADR and
  change plan per `SCOPE.md` (Environment boundaries) and ADR-0003 §5.
- Creation of any empty `production/<cc>/<site-id>/` directory (prohibited by
  AGENTS §2 — no speculative stubs).
- Live Journey of Life assets (`pve-prod-hv01`, `prox01`, `pbs01`, etc.) — owned
  by `journeyoflife-org/jol-infrastructure`; not recorded, moved or renamed
  here (ADR-0003 §6).
- ADR-0002 (multi-project architecture) — a **separate change class**, not
  bundled into this PR.
- Any secret, credential, IP address, MAC, serial or asset ID.

## 4. Maintenance window

Not applicable. This change mutates **no running system**; the only effect is on
the Git repository and GitHub PR review. No device is reachable, reachable-only,
or modified, so no outage/degraded window is required. The control is PR review
+ required status checks (`validate.yml`), not a maintenance window.

| Field | Value |
| --- | --- |
| Start (ISO-8601, with timezone) | Not applicable — no execution against devices |
| End (ISO-8601, with timezone) | Not applicable |
| Expected duration | PR review time only |
| Service impact | none |
| Affected services | none |
| Communication sent to | Not applicable (team/role; no operational notice required) |

## 5. Prerequisites

Each item is a stop condition; if false at merge time, do not merge.

- [ ] ADR-0003 is at least `Proposed` and its open implementation items (1–4) are
      acknowledged by the executor; none of them block *recording* the
      convention, only first *use*.
- [ ] The PR introduces **no** `asset_id:` / host / IP / credential value under
      `inventories/production/**` (verified — README is prose only).
- [ ] `docs/adr/README.md` index has **no dead link** to a file excluded from
      this PR (ADR-0002 is excluded → its row must be omitted, keeping 0001 +
      0003).
- [ ] `host_vars` naming invariant is documented correctly: the file name equals
      `inventory_hostname`, **not** the asset ID (ADR-0003 §3).
- [ ] Offline gates green (§6): detect-secrets, yamllint, syntax-check, offline
      fixture, ansible-lint `--profile production`.
- [ ] The `change-scope` guard passes for this diff (`check_change_plan.py`, §8).
- [ ] Approved by the CODEOWNERS-required reviewers for the touched paths.
      **Gap:** those teams do not yet exist (§9) — approval is not obtainable in
      the current org state.
- [ ] Credentials: none required (no device access).

## 6. Pre-flight checks

Evidence captured on a clean export of the candidate (working-tree content,
never a harness-exercised copy) using the CI-matched toolchain
(Python 3.12.16, ansible-core 2.17, detect-secrets 1.5.0, yamllint,
Galaxy collections path). Expected results shown; paste actual on merge.

```
python .github/scripts/detect_secrets_check.py
yamllint -s -c .yamllint.yml ansible/ inventories/ .github/workflows/ provisioning/
ansible-playbook -i inventories/lab/hosts.yml --syntax-check ansible/playbooks/baseline-hosts.yml
ansible-inventory -i inventories/lab/hosts.yml --graph
ansible-playbook -i ansible/tests/offline/inventory.yml ansible/tests/offline/baseline-offline.yml
ansible-lint --profile production --nocolor --exclude collections/   # run from ansible/
```

| Check | Command | Expected | Actual (paste) |
| --- | --- | --- | --- |
| Secret scan | `detect_secrets_check.py` | "No secrets detected", rc=0 | TODO(<executor-role>) |
| YAML lint | `yamllint -s …` | rc=0 (warnings allowed on pre-existing files) | TODO(<executor-role>) |
| Syntax | `--syntax-check` lab | playbook parses, rc=0 | TODO(<executor-role>) |
| Offline fixture | `baseline-offline.yml` | `failed=0 unreachable=0`, rc=0 | TODO(<executor-role>) |
| Ansible lint | `--profile production` | "Passed: 0 failure(s), 0 warning(s)", rc=0 | TODO(<executor-role>) |

## 7. Apply steps

Ordered, idempotent, reversible (all are Git operations; no device gate).

| # | Step | Command | Gate variable | Reversible? |
| --- | --- | --- | --- | --- |
| 1 | Branch from the merged base | `git switch -c feat/country-first-inventory <base>` | n/a | Yes (delete branch) |
| 2 | Stage the in-scope file set (explicit paths) | `git add <files>` | n/a | Yes (`git restore --staged`) |
| 3 | Commit | `git commit -m "inventory: country-first convention (ADR-0003)"` | n/a | Yes |
| 4 | Push + open PR against the correct base | `git push` / `gh pr create --base <base>` | n/a | Yes |
| 5 | Merge after review + green checks | `gh pr merge` | reviewer approval + `validate.yml` | Yes (revert, §10) |

Base note: target `origin/main` **only after PR #1 (baseline import) merges**;
while `main` remains the empty bootstrap, base on `origin/import/initial-baseline`
so the tracked files this convention edits actually exist.

## 8. Verification

| Check | Command / observation | Success criterion | Evidence link |
| --- | --- | --- | --- |
| Change-scope guard | `python .github/scripts/check_change_plan.py --base <base> --head <head>` | "Change-plan requirement satisfied", rc=0 | TODO(<executor-role>) |
| Production README present | `gh api repos/.../contents/inventories/production` | README exists; no host/asset file | TODO(<executor-role>) |
| No accidental site dir | `git ls-files inventories/production/` | only `README.md` tracked | TODO(<executor-role>) |
| ADR index link integrity | open `docs/adr/README.md` on the merged tree | no link to a file absent in the tree | TODO(<executor-role>) |
| Full CI | `validate.yml` on the PR | all required checks green | PR checks page |

Evidence is stored in the restricted evidence store named in §10.3, **not**
committed to Git.

## 9. Stop conditions

- If the change-scope guard fails → **abort merge**, fix the plan/class/coverage.
- If any secret-scan or lint gate regresses → **abort**, do not allow-list
  without a CODEOWNER-approved comment (AGENTS §5).
- If a reviewer cannot be assigned because `@custos-arcae/platform-leads`,
  `security-reviewers`, or `site-lt-vilnius` teams do not exist → **merge is
  blocked**; this is a governance prerequisite, not a technical failure.
- **Approval-independence gap:** the org currently has a single member who is
  also the author, and GitHub forbids author self-approval. A normal merge is
  unreachable until a second, independent account exists or the owner records an
  ADR-based governance decision. Do **not** bypass with `--no-verify`, force
  push, or an undocumented admin override (AGENTS §1.4, §8).
- If this PR is found to also change `inventories/production/**` beyond the
  placeholder README (e.g. adding a host) → **abort**; that requires a real
  commissioning plan and window.

## 10. Recovery

### 10.1 Rollback path

The change is documentation-only, so rollback is a clean revert.

| # | Step | Command | Owner |
| --- | --- | --- | --- |
| 1 | Revert the merge commit | `git revert -m 1 <merge-sha>` then PR the revert | `@custos-arcae/platform-leads` |
| 2 | Confirm tree | `git show <base>:docs/adr/README.md` has no dangling link | `@custos-arcae/platform-leads` |

Executable by the rollback owner without the executor present.

### 10.2 Worst case

- Worst case: a stale convention/ADR reference is left in the tree after revert.
- Decision point: within the review window, before any site is commissioned.
- Time budget: trivial (docs-only); no data or service is at risk.
- Escalation: re-open a corrective docs PR; no operational escalation required.

### 10.3 Evidence store

| Artefact | Location | Access |
| --- | --- | --- |
| Pre-change export + gate output | restricted evidence store (not Git) | executor/approver roles |
| CI run logs | GitHub Actions run for the PR | org members |
| Vendor case ID (if any) | N/A | N/A |

## 11. Rollback deadline

| Field | Value |
| --- | --- |
| Rollback owner | `@custos-arcae/platform-leads` (role) |
| Decision deadline (ISO-8601) | `TODO(<executor-role>): set to merge date + 5 business days` |
| After deadline | forward repair (a follow-up docs PR) |

## 12. Post-execution

- [ ] Verification evidence attached to §8.
- [ ] Audit log reviewed (none expected — no device access).
- [ ] Monitoring N/A (no service change).
- [ ] This plan status updated to Executed / Rolled back / Cancelled.
- [ ] `CHANGELOG.md` updated if operator-visible (naming convention is
      operator-visible → yes).
- [ ] Lessons learned *(optional)*:

## 13. Approvals

| Role | Team / handle | Decision | Date |
| --- | --- | --- | --- |
| Executor | `@custos-arcae/platform-leads` | Pending | |
| Approver | `TODO(<owner-role>)` | Pending | |
| Security reviewer | `@custos-arcae/security-reviewers` (team does not yet exist — see §9) | Blocked | |
| Site owner (production only) | `@custos-arcae/site-lt-vilnius` (team does not yet exist — see §9) | Blocked | |

---

### Compliance mapping *(auto-filled by the template author, do not edit per-plan)*

| Control | Section |
| --- | --- |
| SOC 2 CC8.1 (change management) | §0, §1, §4, §7, §10, §13 |
| SOC 2 CC7.2 (monitoring) | §8, §9, §12 |
| ISO 27001 A.8.32 (change management) | §0, §7, §10, §13 |
| ISO 27001 A.5.24 (incident management) | §9, §10.2, §11 |
| ISO 27001 A.8.16 (monitoring activities) | §8, §12 |
| GDPR Art. 5(1)(c) (data minimisation) | §1 (roles, not persons), §10.3 (restricted evidence store) |
| GDPR Art. 32 (security of processing) | §5, §6, §10 |
