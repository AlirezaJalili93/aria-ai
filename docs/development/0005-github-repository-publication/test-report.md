# Test Report: 0005 GitHub Repository Publication

[Development record](./development.md)

## Environment

- Date: 2026-08-17
- OS: Windows
- GitHub CLI: 2.96.0
- Authenticated owner: `AlirezaJalili93`
- Repository: `AlirezaJalili93/aria-ai`
- Visibility: `PRIVATE`
- Default branch: `main`

## Test Cases

| Test ID | Requirement | Test | Expected result |
|---|---|---|---|
| TC-0501 | REQ-010 | GitHub authentication and repository ownership | CLI is authenticated as `AlirezaJalili93` |
| TC-0502 | REQ-010 | Remote repository metadata | Repository exists with private visibility and `main` default branch |
| TC-0503 | REQ-011 | Publication-scope audit | All source-controlled project files are tracked; generated/local artifacts are ignored |
| TC-0504 | REQ-011 | Secret and oversized-file scan | No credential/private-key pattern and no oversized publishable file is found |
| TC-0505 | REQ-013 | Complete project quality gate | Lint, types, tests, builds, and architecture validation pass |
| TC-0506 | REQ-011 | Push and remote parity | Local `HEAD`, upstream, and `origin/main` resolve to the same commit |
| TC-0507 | REQ-012 | Final evidence and repository state | Development/test records validate and the final worktree is clean |

## Execution Results

| Test ID | Command or method | Actual result | Status |
|---|---|---|---|
| TC-0501 | `gh auth status` and `gh api user` | Authenticated through the system keyring as `AlirezaJalili93`; required `repo` scope present | PASS |
| TC-0502 | `gh repo view AlirezaJalili93/aria-ai` | Repository exists at `https://github.com/AlirezaJalili93/aria-ai` with `PRIVATE` visibility and `main` default branch | PASS |
| TC-0503 | `git ls-files`, `git check-ignore`, staged path review | 78 baseline files plus 2 evidence files published; dependencies, `.env`, caches, virtual environments, `.tools`, `.next`, and build metadata excluded | PASS |
| TC-0504 | Publishable-file size audit and credential-pattern scan | Largest baseline file was 227,492 bytes; no token, secret-key, or private-key marker matched | PASS |
| TC-0505 | `npm run quality` | Web/API/Worker lint and types passed; 13 tests passed; all builds passed; 20 architecture checks passed | PASS |
| TC-0506 | `git rev-parse HEAD`, `git rev-parse @{u}`, `git ls-remote origin refs/heads/main` | Local HEAD, configured upstream, and remote main SHA matched after the final push | PASS |
| TC-0507 | Record validator, `git status -sb`, and final GitHub metadata read | Evidence accepted, branch tracks `origin/main`, and the final worktree is clean | PASS |

The initial HTTPS push failed before transfer because of a transient connection timeout. A controlled retry succeeded; subsequent upstream and SHA checks passed.

## Final Status

**Final status:** PASS
