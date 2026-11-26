# GitHub administrator checklist: authorization enforcement

| | |
| --- | --- |
| Purpose | What an **authorized GitHub administrator** must configure and verify before production commissioning can be enabled. |
| Audience | Repository/organization administrator (not the operator, not an AI agent). |
| Authority | `AGENTS.md` §5.1 (Authorization enforcement model), `.github/CODEOWNERS`. |

> **The reviewer/agent does not change any GitHub setting.** This checklist is
> for a human administrator. Nothing here is verifiable from inside the
> repository; a green CI run proves only the *repository-guard* layer
> (`AGENTS.md` §5.1), never human authorization. Production stays disabled
> (`custos_production_commissioning_enabled=false`) until every box below is
> confirmed and recorded.

---

## 1. Team handles and membership

`.github/CODEOWNERS` currently uses **placeholder** team slugs (see its
`TODO(platform-leads)` header). Before enforcement means anything:

- [ ] Replace every placeholder with the **real** team slug. Confirm each exists
      in the organization:
      ```bash
      gh api orgs/custos-arcae/teams/<slug> --jq '.slug,.name,.privacy'
      ```
- [ ] Confirm each named team has **explicit write access** to this repository.
      A CODEOWNERS line naming a team without write access is **silently
      ignored** by GitHub — it does not error, it just never assigns a reviewer.
      ```bash
      gh api repos/custos-arcae/custos-arcae-control/teams --jq '.[].slug'
      # each CODEOWNERS team must appear here with push permission
      gh api repos/custos-arcae/custos-arcae-control/teams/<slug>/permission --jq '.permission'
      ```
- [ ] Teams referenced by CODEOWNERS (verify each): `platform-leads`,
      `security-reviewers`, `hardware-owners`, `virtualisation-owners`,
      `backup-owners`, `network-owners`, `observability-owners`,
      `site-lt-vilnius`.
      `TODO(admin): confirm the actual slugs and record them here.`
- [ ] Record the confirmation (who, when, which slugs) in the change plan /
      restricted store — **not** as personal data in Git.

## 2. Repository permissions

- [ ] No collaborator has direct admin/write access bypassing the teams above.
      ```bash
      gh api repos/custos-arcae/custos-arcae-control/collaborators --paginate \
        --jq '.[] | "\(.login) \(.role_name)"'
      ```
- [ ] `Restrict who can push to matching branches` is enabled for `main`.
- [ ] Force pushes and branch deletion are **disabled** for `main`.
- [ ] The repository requires **signed commits** if that is org policy
      (`AGENTS.md` §1.4 forbids `--no-verify` and direct pushes to `main`).

## 3. Branch protection on `main`

- [ ] Protection rule matches `main` (and any release branch).
- [ ] **Require a pull request before merging** — enabled.
- [ ] **Require approvals** — set the count (see §4 for why a count alone is not
      enough).
- [ ] **Dismiss stale pull request approvals when new commits are pushed** —
      enabled.
- [ ] **Require review from Code Owners** — enabled.
- [ ] **Require approval of the most recent review** — enabled.
- [ ] **Require status checks to pass before merging** — enabled, with the
      checks named in §5.
- [ ] **Require branches to be up to date before merging** — enabled.
- [ ] **Do not allow bypassing the above settings** — enabled (include
      administrators), or explicitly record who may bypass and why.

## 4. If EVERY named team must approve (critical nuance)

`/inventories/production/**` lists **three** teams in CODEOWNERS
(`platform-leads`, `security-reviewers`, `site-lt-vilnius`). GitHub CODEOWNERS
semantics are:

- **last-match-wins** across lines;
- a single matching line is satisfied when **any ONE** of its listed owners
  approves — it does **NOT** require all listed teams;
- a **generic "required approvals = N"** count does **NOT** establish *which*
  teams approved. N approvals from the same team satisfy the count.

Therefore, to make **each** of the three teams independently required:

- [ ] Do **not** rely on the CODEOWNERS line plus an approval count. Choose one
      of these enforceable designs and record which was used:
      1. **Split by path** so each sensitive path maps to exactly **one** owning
         team in CODEOWNERS, then rely on *Require review from Code Owners*.
         With one team per path, that team is independently required.
         (`TODO(admin): restructure the production paths accordingly, via a
         CODEOWNERS PR reviewed by security-reviewers.`)
      2. **Add a required status check per team** — e.g. a `CODEOWNERS`-aware
         check or a manual `/approve-<team>` gate — so each team's sign-off is a
         distinct required check that cannot be satisfied by another team.
      3. Use an **external required check** (CI or a governance bot) that fails
         unless it observes an approving review from *each* required team slug
         on the head SHA, and mark that check required.
- [ ] Verify the chosen design by opening a test PR that touches
      `/inventories/production/` and confirming it **cannot** merge with
      approvals from fewer than all required teams.
- [ ] Record the verification (test PR number, which teams were missing, that
      merge was blocked) in the restricted store.

> A single "approvals ≥ 3" setting is **not** evidence that platform-leads AND
> security-reviewers AND site-lt-vilnius each approved. Do not treat it as such.

## 5. Required status checks

Mark as **required** the checks that **always run**. The `validate` workflow
runs on `pull_request` only (`AGENTS.md` §5). Job display names:

| Job (`name:`) | Always runs? | Safe to mark required? |
| --- | --- | --- |
| `Change scope guard` | Yes | **Yes** |
| `Secret scan` | Yes (needs change-scope) | **Yes** |
| `YAML & structure` | Yes (needs change-scope) | **Yes** |
| `Ansible lint & offline checks` | **Conditional** (`if: touches_ansible || touches_inventory`) | See caveat |
| `Python lint & tests` | **Conditional** (`if: touches_python`) | See caveat |

- [ ] Mark `Change scope guard`, `Secret scan`, `YAML & structure` as required.
- [ ] **Caveat — conditional jobs as required checks:** a required check whose
      job is skipped by its `if:` condition never reports a status, so GitHub
      can hold the PR as *pending* indefinitely. Before marking
      `Ansible lint & offline checks` or `Python lint & tests` required, either
      (a) make the job always run (drop/relax the `if:` via an ADR — `AGENTS.md`
      §8), or (b) leave them non-required and rely on the always-run guards plus
      CODEOWNERS review. Record the decision.
      `TODO(admin): decide and record; do not weaken CI without an ADR.`

## 6. Secret scanning and push protection

- [ ] GitHub **secret scanning** is enabled for the repository.
- [ ] **Push protection** is enabled (blocks pushes containing detected
      secrets), complementing the CI `gitleaks` + `detect-secrets` jobs.
- [ ] Confirm the CI `Secret scan` job fails on any finding
      (`.github/scripts/detect_secrets_check.py` exits non-zero on findings AND
      on scanner error — verified offline).

## 7. CODEOWNERS file protection

- [ ] `/.github/CODEOWNERS` is itself owned by `@custos-arcae/security-reviewers`
      (already declared) and protected so it cannot be weakened without an
      owner's approval.
- [ ] `/.github/workflows/` requires `security-reviewers` (already declared).
- [ ] Confirm no rule in CODEOWNERS was broadened to `all` or relaxed
      (`AGENTS.md` §1.2 forbids weakening production gating).

## 8. Final gate before enabling production

Only when **all** of the above are confirmed and recorded may an authorized
operator, inside a booked maintenance window with an approved change plan, run
production commissioning by passing
`-e custos_production_commissioning_enabled=true` **and**
`-e custos_change_plan=docs/change-plans/YYYYMMDD-<slug>.md`. Even then:

- the flag is **necessary but not sufficient**;
- a matching change-plan **filename** is a necessary check only and never
  authorizes an execution on its own (`baseline-hosts.yml` pre_tasks state this
  explicitly);
- approval is enforced by the CODEOWNERS review + branch protection configured
  above and by the approver role named in the plan.

Until this checklist is complete, production commissioning **stays disabled**.

## 9. Revision history

| Date | Revision | Author (role) | Notes |
| --- | --- | --- | --- |
| 2026-11-24 | 1.0 | `platform-leads` | Initial GitHub administrator authorization checklist. |
