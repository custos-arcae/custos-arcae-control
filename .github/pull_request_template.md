<!--
Pull request template for custos-arcae-control.

Every section is mandatory unless it is explicitly marked optional. Reviewers
are expected to close PRs that leave sections blank or answer "N/A" without
justification. See AGENTS.md for the review contract.
-->

## Summary

<!-- One paragraph: what changes, and why now. Link the issue or change plan. -->

- Change class: <!-- one of: host-baseline | proxmox-ve | proxmox-backup | management-network | switch | monitoring | verify | docs | ci -->
- Change plan: <!-- path under docs/change-plans/, or "not required" with justification -->
- Runbook: <!-- path under docs/runbooks/, or "not required" with justification -->

## Scope check

- [ ] I have read `SCOPE.md` and this change is in scope.
- [ ] This PR contains exactly one change class (no mixed concerns).
- [ ] No speculative stubs, empty directories, or unimplemented placeholders.

## Compliance

- [ ] No secrets, tokens, keys, certificates, recovery seeds or vault
      passwords are present in the diff (including in comments and examples).
- [ ] No personal data (natural-person names, personal emails, personal phone
      numbers) is present in the diff. Ownership is expressed as role/team.
- [ ] Production paths (`inventories/production/**`) are only touched with a
      filed change plan linked above.
- [ ] CI (`.github/workflows/**`) is not given access to production
      credentials.
- [ ] CODEOWNERS is not weakened.

## Ansible quality (skip if not applicable)

- [ ] Roles are site-agnostic; site-specific values live in inventory.
- [ ] Fully qualified collection names used (`ansible.builtin.*`).
- [ ] Every task has a `name:`; reboots are gated by a variable defaulting to
      `false`.
- [ ] Handlers are used for service restarts and reboots.
- [ ] No `ignore_errors: true` on state-mutating tasks.
- [ ] `ansible-lint --profile=production` passes locally.

## Verification

<!-- How will the executor prove the change worked? Cite the runbook section
and paste the expected evidence. -->

- Target environment: <!-- lab | production/lt/lt-vilnius-01 (country-first, ADR-0003) -->
- Target devices: <!-- asset IDs or hostnames; never invent values -->
- Success criteria:
- Evidence to capture (logs, command output, screenshots of console, etc.):

## Recovery

<!-- What happens if this goes wrong? Link the runbook recovery section and
state the worst-case path. -->

- Stop conditions:
- Rollback path:
- Worst case (rebuild / forward repair / restore from backup):
- Rollback owner (role, not person):
- Rollback deadline:

## Reviewer checklist

- [ ] CODEOWNERS-required reviewers are all assigned.
- [ ] Change plan (if required) is filed and linked.
- [ ] Runbook (if required) exists and matches the change.
- [ ] CI is green, including secret scan.
- [ ] For lab-affecting changes: lab evidence is attached or linked.
- [ ] For production-affecting changes: maintenance window is booked and
      out-of-band console access is confirmed reachable.

## Optional: notes for reviewers

<!-- Anything non-obvious: version pins, vendor caveats, tested installer
builds, known limitations. -->
