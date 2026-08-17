# Development Record: 0006 CI Baseline

- Increment ID: `0006-ci-baseline`
- Date: 2026-08-17
- Owner: Codex (implementation and senior review)
- Related plan/issue: Sprint 1 backlog story `S1-A02 — CI Baseline`
- [Test report](./test-report.md)

## Scope

Establish the documented pull-request CI baseline for the existing GitHub repository: lint, type-check, unit/API/worker tests, builds, architecture/contract validation, secret scanning, dependency scanning, dependency caches, persistent failure evidence, pull-request governance, and enforced green checks before merge. This increment does not add product behavior, UI, a database migration, or a deployable service.

## Source Documents

- Google Drive `Aria AI/Dev/Engineering Planning/Sprint 1 Backlog` — story `S1-A02`.
- Google Drive Master Execution Plan.
- Google Drive Repository Specification.
- Google Drive Deployment Runbook.
- Google Drive Test Strategy.
- Google Drive Security and Compliance Baseline.
- Google Drive Dependency Version Register.
- Repository `AGENTS.md`.
- [System architecture](../../architecture/system-architecture.md).
- [Document-driven development policy](../../governance/document-driven-development.md).
- User instruction on 2026-08-17 authorizing the repository visibility change from private to public after GitHub rejected protection features for the private repository.
- User-provided `ui-ux-pro-max.md` and `design-system.md`, used as unchanged UI quality guardrails; this increment contains no UI change.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-014 | S1-A02: lint, type-check, unit/API tests, dependency scan, build | `.github/workflows/ci.yml`, existing `npm run quality`, `scripts/scan-dependencies.mjs` | TC-0601, TC-0603, TC-0604 |
| REQ-015 | S1-A02: a PR without green CI cannot merge | Strict `main` branch protection requiring `Quality` and `Security baseline`, enforced for administrators | TC-0607 |
| REQ-016 | S1-A02: active cache and preserved run evidence | Official npm/uv caches and `if: always()` quality/security artifact uploads | TC-0601, TC-0605 |
| REQ-017 | Runbook/Test Strategy/Security: architecture, contract, secret, and dependency gates | `npm run quality`, `scripts/scan-secrets.mjs`, `scripts/scan-dependencies.mjs`, immutable Action refs | TC-0601, TC-0602, TC-0603, TC-0604 |
| REQ-018 | Repository Specification: PR evidence and higher-risk ownership | `.github/pull_request_template.md`, `.github/CODEOWNERS` | TC-0606 |
| REQ-019 | Standing rule: development/test Markdown and senior review | This record, linked report, validation extensions, ADR-005 | TC-0608 |

## Assumptions and Clarifications

**Unapproved assumptions:** None

- GitHub Actions was selected because the approved project repository is hosted on GitHub and the repository specification requires GitHub pull-request governance.
- Exact runtime pins are taken from the approved dependency register and existing repository baseline.
- The private repository could not enable Branch Protection or Rulesets: both APIs returned `HTTP 403` requiring GitHub Pro or public visibility. The user explicitly selected public visibility; no visibility change was inferred.

## Changes

- Added `.github/workflows/ci.yml` with independent `Quality` and `Security baseline` jobs for pull requests and `main`.
- Added exact `.node-version`, exact uv/pip-audit versions, and immutable full-SHA references for all third-party Actions.
- Added npm and uv dependency caches, concurrency cancellation, read-only contents permission, timeouts, and always-uploaded quality/security artifacts.
- Added repository-owned publishable-file secret scanning that reports detector/path/line without returning the matched value.
- Added npm plus independent API/worker lockfile audits and persistent machine-readable reports.
- Added CI configuration and secret-scanner positive/negative tests.
- Added a PR template and CODEOWNERS coverage for the repository, CI, migrations, architecture, and security paths.
- Extended `package.json`, the architecture fitness validator, repository README, and development-record index.
- Added [ADR-005](../../adr/ADR-005-ci-baseline.md).
- Changed `AlirezaJalili93/aria-ai` from private to public with explicit user authorization and enabled strict `main` protection.

## Architecture and Design Decisions

- CI remains repository tooling and introduces no new deployable service or cross-module dependency.
- The existing `npm run quality` stays the single quality composition point so local and CI behavior cannot drift silently.
- Secret findings deliberately omit matching content to keep CI logs and JSON artifacts from reproducing credentials.
- Python audit is a CI tool invoked with an exact version through uv and is not added to runtime lockfiles.
- Consequential CI/governance decisions and their tradeoffs are recorded in ADR-005.

## Structure Preservation

- Modular-monolith application, domain, and infrastructure boundaries are unchanged.
- No endpoint, event contract, migration, worker framework, product flow, design token, or UI file changed.
- The documented repository topology is preserved; additions are limited to `.github`, repository scripts/tests, ADRs, and the established development-record path.
- RTL, LTR, accessibility, token, and responsive rules remain unchanged and continue to be checked by the existing web tests and architecture validator.

## Senior Review

- **Resolved — Windows portability:** direct `npm.cmd` execution from Node returned `EINVAL`; dependency scanning now invokes the npm CLI through the active Node executable on Windows and uses `npm` on Linux CI.
- **Resolved — diagnostic quality:** initial process failures produced empty audit logs; spawn errors are now included in the retained dependency log.
- **Resolved — secret-test isolation:** a credential-shaped fixture was initially discoverable by the repository-wide scanner; test material is now assembled at runtime so the test validates detection without publishing a credential-shaped literal.
- **Resolved — test expectation:** the environment detector correctly emitted one finding for `SERVICE_TOKEN`; the duplicate expected finding was removed.
- **Resolved — GitHub enforcement:** private-repository protection and Rulesets both returned `HTTP 403`. After explicit user approval, visibility was changed to public and strict protection was created and read back successfully.
- Verified immutable Action SHAs, minimum GitHub permissions, job timeouts, cache configuration, failure artifact behavior, scan output confidentiality, command exit propagation, and protection against force-push/delete.
- No unresolved severity-high, medium, or low implementation finding remains.

## Verification

- CI configuration tests: 7/7 passed.
- Full repository tests: 20/20 passed.
- Web, API, and worker builds passed.
- Secret scan inspected 90 publishable text files with zero findings before final evidence files were added.
- npm reported 0 vulnerabilities across 428 dependencies; pip-audit reported no known vulnerabilities in the API or worker lockfile exports.
- GitHub reported `PUBLIC` visibility and strict required contexts `Quality` and `Security baseline`, enforced for administrators.
- Final command and hosted-CI evidence is recorded in [test-report.md](./test-report.md).

## Remaining Risks

- The baseline pattern scanner examines current publishable files, not full Git history. GitHub-hosted secret scanning and credential rotation remain necessary if a real credential is ever committed.
- Action SHA updates and pip-audit version updates are intentional maintenance changes and must be reviewed with their release notes.
