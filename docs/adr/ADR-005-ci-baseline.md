# ADR-005: GitHub Actions CI Baseline

- **Status:** Accepted
- **Date:** 2026-08-17
- **Story:** S1-A02 — CI Baseline

## Context

The Sprint 1 backlog requires lint, type-check, unit test, API test, dependency scan, build, active caches, and preserved run evidence. The deployment runbook makes a green pull-request gate mandatory and also requires architecture, secret, dependency, and contract checks when applicable. The repository is hosted on GitHub, uses npm workspaces for the web application, and uses independent uv lockfiles for the API and worker.

## Decision

1. Use a single GitHub Actions workflow with two required job identities: `Quality` and `Security baseline`.
2. Run CI for pull requests targeting `main` and pushes to `main`, with read-only repository contents permission and cancellation of superseded runs.
3. Run the existing `npm run quality` command as the quality gate. It covers lint, type-check, all unit/API/worker tests, builds, contract checks, and architecture fitness validation.
4. Add repository-owned secret scanning for publishable files and dependency auditing for npm plus both Python lockfiles. The CI-only Python audit tool is invoked at an exact version and is not added to either runtime dependency graph.
5. Pin Node.js, Python, uv, pip-audit, and every third-party GitHub Action. Action references use immutable commit SHAs.
6. Enable official npm and uv caches and upload quality and security reports with `if: always()` so failure evidence remains available.
7. Add a pull-request template and CODEOWNERS coverage for repository-wide review and higher-risk migration, architecture, security, and CI paths.

## Consequences

- A failed quality or security job provides a stable check name that branch protection can require.
- CI does not add a deployable service or change modular-monolith boundaries.
- The repository owns a small conservative secret-pattern scanner; new credential formats require a detector and a test.
- Dependency reports and quality logs are retained as per-run GitHub artifacts, while `.data/` remains local-only.
- Branch protection is configured in GitHub after both job identities have completed successfully on the implementation pull request.

## Source documents

- Sprint 1 Backlog — S1-A02
- Master Execution Plan
- Repository Specification
- Deployment Runbook
- Test Strategy
- Security and Compliance Baseline
- Dependency Version Register
- [System architecture](../architecture/system-architecture.md)
