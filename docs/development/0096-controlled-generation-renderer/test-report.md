# Test Report: 0096 Controlled Generation Renderer

- Increment ID: `0096-controlled-generation-renderer`
- Date: 2026-10-10
- [Development record](./development.md)

## Environment

- Windows / PowerShell
- Node.js 24 / npm 11
- React 19 static rendering
- Existing Persian synthetic fixtures only
- Customer content / real Provider / hosted execution: not used

## Test Cases

| Test | Requirement | Expected result | Status |
|---|---|---|---|
| TC-9601 | REQ-9601 | Candidate AST is rejected before rendering | PASS |
| TC-9602 | REQ-9601, REQ-9604, REQ-9606 | Repeat canonical render is identical with one main and hidden h1 | PASS |
| TC-9603 | REQ-9602, REQ-9604, REQ-9607 | Three Project Types cover all fourteen controlled Components | PASS |
| TC-9604 | REQ-9605 | Static SimpleForm has no form/action/method/name/submit network surface | PASS |
| TC-9605 | REQ-9603 | Unknown and remote Assets fail closed before markup | PASS |
| TC-9606 | REQ-9606 | Navigation outside exact AST Page paths fails closed | PASS |
| TC-9607 | REQ-9602 | React escapes markup-like text and source has no execution escape hatch | PASS |
| TC-9608 | REQ-9608 | Full lint/typecheck/test/build/validate gates pass | PASS |

## Commands and Results

```text
npm test --workspace @aria/generation-renderer
PASS — 8 tests

npm run lint --workspace @aria/generation-renderer
PASS — zero warnings

npm run typecheck --workspace @aria/generation-renderer
PASS

npm run lint
PASS — Renderer/Web ESLint; API/Worker Ruff

npm run typecheck
PASS — Renderer/Web TypeScript; API 194 and Worker 81 Python source files

npm run build
PASS — Renderer declarations/ESM; production Web; API/Worker compile

npm test (with repository-local ignored TEMP/TMP on Windows)
PASS — Records 6; Generation Output 4; Renderer 8; CI 213; Eval 35; Web 47;
       API 543 passed / 175 environment-gated skipped;
       Worker 208 passed / 36 environment-gated skipped

npm run validate
PASS — repository validation completed
```

## Environmental Retry Evidence

The first full `npm test` reached the Worker suite and encountered Windows `PermissionError` while
Pytest scanned the shared `%TEMP%\pytest-of-A.Jalili` directory. The same Worker suite passed
`208 passed / 36 skipped` after setting `TEMP` and `TMP` to an ignored repository-local `.data`
directory. The entire `npm test` command was then rerun from the beginning with that isolated temp
root and passed. No source, test expectation or product behavior was changed to address the
environmental failure.

## Security and Accessibility Evidence

- Candidate input, invalid navigation and unauthorized/remote Assets fail before output.
- No HTML injection, iframe, dynamic import, network fetch or raw Asset-to-src path exists.
- Every Page independently has one `main` and one accessibility-tree `h1`; fixed hidden headings use
  clipping rather than `display:none` or `aria-hidden`.
- `SimpleForm` has no `form` element or submit-capable metadata and therefore cannot issue a static
  GET/POST without hydration.

## Execution Results

- All three existing Persian synthetic Project Types rendered successfully as independent Pages;
  their combined section set exercised every one of the fourteen Registry Components.
- Candidate input, unresolved navigation, empty/remote/data Asset resolution and markup-like text
  followed the expected fail-closed or escaped paths.
- The same canonical Page produced byte-identical static structural markup on repeated rendering.
- Package and repository lint, strict typecheck, production build, complete tests and architecture
  validation passed after the documented Windows temp-directory retry.

## Final Status

**Final status:** PASS
