# Change plan: <short title>

> Copy this file to `docs/change-plans/YYYYMMDD-<slug>.md` and fill in every
> section. Sections marked *(optional)* may be omitted with justification.
> A change plan with blank mandatory sections will be rejected in review.
>
> See [`AGENTS.md`](../../AGENTS.md) §6 for the rules this template enforces.

## 0. Identification

| Field | Value |
| --- | --- |
| Change plan ID | `YYYYMMDD-<slug>` |
| Title | |
| Change class | host-baseline / proxmox-ve / proxmox-backup / management-network / switch / monitoring / verify / docs / ci |
| Environment | lab / production/lt-vilnius-01 |
| Runbook | path under `docs/runbooks/`, or "none" with justification |
| ADR (if required) | path under `docs/adr/`, or "not required" |
| PR | link |
| Filed | ISO-8601 date |
| Status | Draft / Approved / Executed / Rolled back / Cancelled |

## 1. Roles

> GDPR: name the **role**, not the person. Individual attribution lives in
> Git commit signatures and PR reviews.

| Role | Team / handle |
| --- | --- |
| Executor | |
| Approver | |
| Rollback owner | |
| On-call during window | |
| Vendor support contact *(optional)* | |

## 2. Objective

One paragraph. What changes, and why now. Link the issue, vendor advisory,
audit finding, or capacity trigger.

## 3. Scope

### 3.1 Target devices

| Asset ID | Hostname | Role in change | Notes |
| --- | --- | --- | --- |
| | | | |

### 3.2 Explicitly out of scope

Name the devices, groups, or change classes this plan does **not** touch.
This prevents scope creep during execution.

- 

## 4. Maintenance window

| Field | Value |
| --- | --- |
| Start (ISO-8601, with timezone) | |
| End (ISO-8601, with timezone) | |
| Expected duration | |
| Service impact | none / degraded / outage |
| Affected services | |
| Communication sent to | (team/role, not individuals) |

## 5. Prerequisites

Each item is a stop condition. If any is false at execution time, abort.

- [ ] Out-of-band console path tested independently of the management network.
- [ ] Known-good configuration saved to restricted storage (SCP export, switch config, PBS policy, etc.).
- [ ] Vendor recovery procedure for the exact version cached locally.
- [ ] Rollback owner reachable and aware of the window.
- [ ] Credentials available in the executor's environment (never in Git).
- [ ] Change plan approved by all CODEOWNERS-required reviewers.
- [ ] Lab evidence attached for the same role/playbook version.
- [ ] *(class-specific)* …

## 6. Pre-flight checks

Commands and expected output. Capture the actual output as evidence.

```
# Example — replace with the real checks for this change class
ansible -i inventories/<env>/hosts.yml <group> -m ping
```

| Check | Command | Expected | Actual (paste) |
| --- | --- | --- | --- |
| | | | |

## 7. Apply steps

Ordered, idempotent, each with a gate variable named.

| # | Step | Command | Gate variable | Reversible? |
| --- | --- | --- | --- | --- |
| 1 | | | | |
| 2 | | | | |

## 8. Verification

How the executor proves the change worked. Cite the runbook section.

| Check | Command / observation | Success criterion | Evidence link |
| --- | --- | --- | --- |
| | | | |

Evidence is stored in the restricted evidence store named in §10, **not**
committed to Git.

## 9. Stop conditions

"If X then abort." Each item names the observer (executor, approver,
monitoring) and the abort action.

- If … then …
- If … then …

## 10. Recovery

### 10.1 Rollback path

The exact steps to return to the pre-change state. Must be executable by the
rollback owner without the executor present.

| # | Step | Command | Owner |
| --- | --- | --- | --- |
| 1 | | | |

### 10.2 Worst case

What happens if rollback is not possible. Name the path: rebuild, forward
repair, restore from backup, vendor RMA. Include the decision point and the
time budget.

- Worst case: 
- Decision point: 
- Time budget: 
- Escalation: 

### 10.3 Evidence store

| Artefact | Location | Access |
| --- | --- | --- |
| Pre-change config export | | |
| Run logs | | |
| Verification screenshots / console captures | | |
| Vendor case ID (if any) | | |

## 11. Rollback deadline

| Field | Value |
| --- | --- |
| Rollback owner | (role) |
| Decision deadline (ISO-8601) | |
| After deadline | forward repair / escalate / accept |

## 12. Post-execution

- [ ] Verification evidence attached to §8.
- [ ] Audit log entries reviewed for unexpected events.
- [ ] Monitoring confirmed healthy for at least 30 minutes after the window.
- [ ] Change plan status updated to Executed / Rolled back / Cancelled.
- [ ] CHANGELOG.md updated if the change is operator-visible.
- [ ] Lessons learned *(optional)*: 

## 13. Approvals

| Role | Team / handle | Decision | Date |
| --- | --- | --- | --- |
| Executor | | | |
| Approver | | | |
| Security reviewer | | | |
| Site owner (production only) | | | |

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
