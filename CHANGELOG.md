# Changelog

All operator-visible changes to `custos-arcae-control` are recorded here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html) where
`MAJOR` indicates a change that breaks existing runbooks or inventory
contracts, `MINOR` adds a new change class, and `PATCH` fixes documentation or
role internals without changing behaviour.

Each entry must link to the change plan under `docs/change-plans/` (or the PR
if no plan is required) and name the affected environments.

## [Unreleased]

### Added
- Repository governance baseline: `README.md`, `SCOPE.md`, `AGENTS.md`,
  `CHANGELOG.md`.
- GitHub governance: `.github/CODEOWNERS`, `.github/pull_request_template.md`,
  `.github/workflows/validate.yml` (YAML validation, ansible-lint, secret
  scan, lab `--check --diff`).
- Lab inventory (`inventories/lab/`) with non-production hosts used to
  validate role and answer-file changes in CI.
- Ansible base configuration: `ansible/ansible.cfg`,
  `ansible/requirements.yml`, `ansible/playbooks/baseline-hosts.yml`.
- First commissioning workflow: role `ansible/roles/dell_host_baseline/`,
  provisioning notes `provisioning/dell/README.md`, and runbook
  `docs/runbooks/commission-dell-host.md`.
- Initial ADR `docs/adr/0001-record-architecture-decisions.md` and change-plan
  template `docs/change-plans/template.md`.

### Environments affected
- `lab` only. No production change in this release.

## [0.1.0] - 2026-11-24

Initial Python helper package skeleton (`src/custos_arcae_control/`, `tests/`,
`pyproject.toml`, `main.py`). No infrastructure workflows yet.

[Unreleased]: https://github.com/custos-arcae/custos-arcae-control/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/custos-arcae/custos-arcae-control/releases/tag/v0.1.0
