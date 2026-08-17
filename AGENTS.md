# Repository instructions

## Product intent

Aria AI turns scattered Persian client input into structured Context, traceable Requirements and Gaps, versioned Scope, controlled Preview/Revision, and exportable delivery. Human review is mandatory at documented critical points.

## Documentation-driven development

- The current approved Google Drive documents under the `Aria AI` project are canonical; repository documents are developer-facing mirrors and must record their source link and sync date.
- Implement only requirements explicitly supported by the current user request or an approved repository document.
- Do not invent product behavior, data fields, UI, integrations, business rules, defaults, limits, technology choices, or acceptance criteria.
- When a required detail is missing, ambiguous, contradictory, or would require an assumption, stop that part of development and ask the user a focused clarification question. Do not silently choose a reasonable default.
- Preserve the documented repository, architecture, domain, contract, template, and design-system structure. Structural changes require explicit user approval and, when consequential, an ADR.
- Before editing, identify the source documents and requirement IDs. After editing, maintain a requirement-to-implementation-to-test traceability table in the increment's `development.md`.
- Record `**Unapproved assumptions:** None` in every completed development record. If this statement is not true, the increment cannot be marked complete.
- Follow the source precedence and conflict process in `docs/governance/document-driven-development.md`.

## Architecture rules

- Preserve the modular-monolith boundaries documented in `docs/architecture/system-architecture.md`.
- Web uses Next.js/React/TypeScript Strict; API and Worker use Python 3.12+/FastAPI-compatible layering. Superseding either stack requires an accepted ADR.
- Domain packages must not import infrastructure or framework code.
- Cross-module writes happen through an application service; asynchronous side effects use the transactional outbox.
- Every mutating public endpoint requires tenant authorization and an idempotency strategy.
- Long-running AI, validation, rendering, and export work belongs in the worker.
- Do not add a new deployable service without an ADR and measurable scaling, isolation, or ownership evidence.

## UI and design-system rules

- Read `design-system/MASTER.md` before adding UI.
- Use primitive -> semantic -> component tokens. Raw color values are allowed only in primitive token definitions.
- Build RTL-first and verify LTR compatibility where relevant.
- Preserve visible focus, semantic controls, accessible names, 44px minimum targets, reduced motion, and WCAG 2.2 AA contrast.
- Use one SVG icon family. Do not use emoji as structural icons.

## Quality gates

- Run `npm test` and `npm run validate`.
- No development increment is complete until both Markdown records exist under `docs/development/<increment-id>/`:
  - `development.md` documents scope, implementation changes, senior review, verification, and remaining risks.
  - `test-report.md` documents test cases, environment, commands, expected/actual results, and final status.
- Use a stable increment ID in the form `NNNN-kebab-case`. Create the records during development and finalize them only after the last test run.
- Link the development record and test report to each other. Do not report completion while either document is missing, stale, or marked PENDING/FAIL.
- A completed `development.md` must identify source documents, contain `REQ-*` traceability, document structure-preservation checks, and confirm that no unapproved assumptions remain.
- `npm run validate` must enforce the development-record convention; never bypass or weaken this gate to finish a change.
- Add or update an ADR when changing a consequential decision.
- Add contract tests before implementing an external integration.
- Treat all Customer Discovery documents as simulated directional evidence until validated with real interviews.
