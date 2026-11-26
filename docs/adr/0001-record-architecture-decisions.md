# ADR-0001: Record architecture decisions

| | |
| --- | --- |
| Status | Accepted |
| Date | 2026-11-24 |
| Deciders | `@custos-arcae/platform-leads`, `@custos-arcae/security-reviewers` (teams, not individuals — GDPR Art. 5(1)(c)) |
| Applies to | `custos-arcae-control` repository |

## Context

`custos-arcae-control` drives changes to production infrastructure under
SOC 2 / ISO 27001 / GDPR obligations. Both frameworks require that
architecturally significant decisions are:

- recorded contemporaneously,
- attributable to a role (not necessarily a named person),
- reviewable by a second party,
- and durable beyond personnel turnover.

Commit messages and PR descriptions are not sufficient: they are scoped to a
single change, they age poorly, and they do not capture the *rejected*
alternatives, which is what a future operator needs when revisiting a
decision under incident pressure.

We also need a lightweight format. A heavyweight template would be skipped
under time pressure, which is worse than no ADR at all.

## Decision

We will use Architecture Decision Records (ADRs) in the style of
[Michael Nygard's original post](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions),
with the following local conventions:

1. **Location.** `docs/adr/NNNN-kebab-case-title.md`. Numbers are
   zero-padded to four digits and never reused.
2. **Immutability.** An accepted ADR is never edited except to change its
   `Status` line. Superseding decisions are recorded in a new ADR that
   names the superseded one.
3. **Status values.** `Proposed`, `Accepted`, `Deprecated`, `Superseded by
   ADR-NNNN`.
4. **Deciders are roles.** Team handles or role names, never natural-person
   names. Attribution to a person lives in Git history and PR reviews, which
   are access-controlled separately.
5. **Required sections.** Context, Decision, Consequences. Optional:
   Alternatives considered, Compliance mapping, Review date.
6. **Review date.** Every ADR carries a `Review date` no more than 12 months
   after acceptance. At review, the deciders confirm the decision still
   holds or open a superseding ADR.
7. **Index.** `docs/adr/README.md` (added when the second ADR lands) lists
   every ADR with status and review date.

### When an ADR is required

- Introducing, removing, or replacing a technology (e.g. choosing Ansible
  over Salt; choosing PBS over restic).
- Changing a trust boundary (e.g. allowing CI to reach a production
  network; adding a new secret store).
- Changing a compliance-relevant default (e.g. relaxing `host_key_checking`,
  enabling IPMI, lowering the TLS floor).
- Adding a new production site.
- Any decision that a future operator would need to understand before
  safely modifying the system under incident pressure.

### When an ADR is NOT required

- Bug fixes inside an existing role.
- Version bumps that do not change behaviour (covered by the PR description
  and CHANGELOG).
- Documentation improvements.
- Inventory value changes (covered by the change plan).

## Consequences

### Positive

- Decisions are discoverable without reading Git history.
- The "alternatives considered" section prevents re-litigating settled
  questions during incidents.
- Role-based attribution satisfies GDPR data-minimisation while preserving
  accountability.
- The 12-month review date forces periodic re-validation, which is an
  ISO 27001 A.5.35 (independent review of information security) artefact.

### Negative

- Writing an ADR takes time. Under incident pressure this may be skipped,
  producing an undocumented decision that is discovered later. Mitigation:
  the PR template asks whether an ADR is required, and reviewers are
  expected to block merges that need one.
- ADRs can accumulate and become stale. Mitigation: the review date and the
  index in `docs/adr/README.md`.
- Role-based deciders can obscure who actually made the call. Mitigation:
  Git commit signatures and PR review records remain the attribution system
  of record for individuals; ADRs deliberately do not duplicate it.

### Neutral

- This ADR (0001) is itself an artefact that must be maintained. If the
  format changes, a superseding ADR is required.

## Compliance mapping

| Control | How this decision satisfies it |
| --- | --- |
| SOC 2 CC3.1 (risk identification) | ADRs record the risk accepted or mitigated by each decision. |
| SOC 2 CC8.1 (change management) | Architecturally significant changes are gated on an ADR. |
| ISO 27001 A.5.35 (independent review) | The 12-month review date and role-based deciders provide independence. |
| ISO 27001 A.8.32 (change management) | ADRs are part of the change record for significant changes. |
| GDPR Art. 5(1)(c) (data minimisation) | Deciders are roles, not natural persons. |
| GDPR Art. 32 (security of processing) | Decisions that alter security posture require an ADR, making them reviewable. |

## Review

Next review due: **2027-11-24**. At review, confirm:

- The ADR format is still being used.
- The index (`docs/adr/README.md`) exists and is current.
- No ADR has passed its review date without action.
