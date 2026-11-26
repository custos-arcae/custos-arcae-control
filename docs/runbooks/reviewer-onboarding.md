# Runbook: Reviewer / CODEOWNER onboarding and confidentiality

> Reusable procedure for granting a **non-author** person review/CODEOWNER access
> to `custos-arcae-control`. Existence of an independent reviewer is what makes a
> normal merge possible under GitHub branch protection and AGENTS.md §5.1
> (human authorization layer). This runbook is the change-class procedure; a
> specific grant is recorded per-person in the restricted evidence store, **not**
> in Git (AGENTS §1.6, GDPR Art. 5(1)(c) — roles/handles, no personal data here).

## 1. Purpose and applicability

Apply whenever adding a reviewer, collaborator, or CODEOWNER team member to the
`custos-arcae` org or the `custos-arcae-control` repository — including a
**not-yet-employee** contributor (future employee, contractor, advisor).

Out of scope: production deployment authorization (see
[`commission-dell-host.md`](commission-dell-host.md)); the deployment-time
change-plan approval, which is a separate human gate.

## 2. Preconditions (all must be true before granting access)

- [ ] The reviewer's GitHub account **exists and is independent** of the author.
      Verify, do not assume:
      `gh api users/<reviewer-github-handle> --jq '{login,id,created_at,type}'`
      — must return `200`, `type=User`, and a `login` **different** from every
      author of the change under review.
- [ ] **Least privilege** is decided first: for a PR approval to count toward the
      required-review gate, **repository Read (pull) is the minimum**. Do not
      grant `write`/`admin` unless the role needs it.
- [ ] A confidentiality / contributor agreement is in place **before or at**
      acceptance (see §4) — the reviewer will see infrastructure planning,
      inventory structure, CODEOWNERS and runbooks.
- [ ] The org owner has explicitly authorized the access change (access changes
      are a human-approval action, never automated).

## 3. Access grant steps

Run as the org owner. `<reviewer-github-handle>` is the verified login.

```bash
ORG=custos-arcae ; REPO=custos-arcae/custos-arcae-control ; REV=<reviewer-github-handle>

# 3.1 Org membership (least privilege: role=member, not admin)
gh api -X PUT "orgs/$ORG/memberships/$REV" -f role=member        # invitation is PENDING until accepted

# 3.2 CODEOWNER team membership (grants AGENTS §5 authority for the mapped paths)
#     platform-leads owns /inventories/lab/** and the global * covering /ansible/**.
gh api -X PUT  "orgs/$ORG/teams/platform-leads/repos/$ORG/custos-arcae-control" -f permission=push
gh api -X PUT  "orgs/$ORG/teams/platform-leads/memberships/$REV" -f role=member

# 3.3 AFTER the invitee accepts (state flips pending->active): request the review
gh pr edit <PR> --repo "$REPO" --add-reviewer "$REV"
```

Notes:
- While an invitation is **`pending`**, GitHub cannot assign the user as a
  reviewer — `gh pr edit --add-reviewer` silently leaves `reviewRequests` empty.
  Poll `gh api "orgs/$ORG/memberships/$REV" --jq .state` until `active`.
- A plain collaborator approval satisfies GitHub's mechanical review count only.
  To also satisfy **AGENTS §5** (CODEOWNER sign-off over scanner allow-lists),
  the reviewer must be a member of the team that CODEOWNERS names for the path.

## 4. Confidentiality expectations (record a signed copy in the evidence store)

> This checklist is procedural guidance, **not legal advice**; the owner should
> have an appropriate agreement reviewed for the jurisdiction. The signed
> per-person copy belongs in the restricted store, never committed to Git.

The reviewer acknowledges, before or at acceptance:

- **No secret ever enters Git.** Credentials are referenced by env-var name /
  Vault path only (AGENTS §1). The reviewer does not add, export, or commit
  secret material, and does not request it.
- **Confidentiality of infrastructure design.** Repository contents (inventory
  layout, network/storage topology, runbooks, change plans) are confidential; no
  disclosure outside authorised team members.
- **Data minimisation / GDPR.** Personal data is not added to issues, PRs,
  inventories, or change plans; ownership is expressed as role/team. Any incidental
  personal data observed is not copied out of the system of record.
- **Independent judgement.** A review reflects the reviewer's own assessment. A
  reviewer who acts on the author's instruction, or under shared credentials, does
  **not** provide the independence this control relies on (see §6).
- **Own credentials + 2FA.** The reviewer uses only their own account with 2FA;
  credentials are never shared with or controlled by the author.
- **Return / revocation.** On role end or departure, org + team memberships are
  removed promptly (§7).

## 5. Responsibilities as a reviewer

- Review the actual diff; do not approve unreviewed or oversized changes.
- For any scanner **allow-list** suppression, confirm it hides an env-var/secret
  **NAME** (never a value) and that removing it re-fails the scan — then APPROVE
  in a way that records the §5 sign-off.
- Comment with specifics; a blank "looks good" does not evidence the control.

## 6. Independence safeguard (the whole point of the gate)

Two distinct accounts are necessary but **not sufficient**. The control is only
real if the reviewer is a distinct human exercising independent judgement under
their own credentials. If the second account is effectively the author's alternate
identity or a rubber stamp, the mechanical gate passes but the SOC 2 CC8.1
segregation-of-duties intent and AGENTS §1.4 ("no self-merge") are **violated**.
When genuine independence cannot be assured, keep the PR blocked and record an
ADR (§8 escalation) rather than fabricate an approval.

## 7. Offboarding

```bash
gh api -X DELETE "orgs/$ORG/teams/platform-leads/memberships/$REV"
gh api -X DELETE "orgs/$ORG/memberships/$REV"
```

- Remove access promptly on departure/role change; note the date in the
  restricted record.
- Rotate any credential the person may have observed through their access.

## 8. Evidence and audit trail

| Artefact | Location | Notes |
| --- | --- | --- |
| Signed confidentiality / contributor acknowledgement | restricted evidence store | **not** in Git (GDPR) |
| Account-independence verification output | restricted evidence store | `gh api users/<handle>` result |
| Access grant / revoke record | org audit log + restricted record | who/when/role |
| Approval + §5 sign-off | the PR review itself | lives in GitHub, referenced by PR link |

## 9. Related

- `.github/CODEOWNERS`, `.github/workflows/validate.yml` (change-scope / secret jobs)
- AGENTS.md §1.4 (no self-merge), §5 (CODEOWNER-approved allow-lists), §5.1 (authorization layers), §6 (change plans)
- `docs/adr/0001-record-architecture-decisions.md` (escalation path if independence is blocked)
