# Development Record: 0049 — Gap Detection Foundation

- **Status:** COMPLETE (S1-J02-A only; full S1-J02 remains incomplete)
- **Increment:** S1-J02-A
- **Source sync date:** 2026-09-09
- [Test report](./test-report.md)

## Scope

Implement the approved provider-neutral Gap Detection foundation: exact Context/Requirement
revision snapshots, candidate validation, provenance and affected-Requirement checks, exact
duplicate rejection, atomic Gap/link persistence, terminal replay (including empty results), Usage
Ledger integration, safe telemetry, and the Critical-rule evaluator boundary.

S1-J02-B (Completion Checklist and deterministic Critical Rule Pack), J03 questions and
Clarifications, public API and UI are explicit non-goals. Full S1-J02 remains incomplete.

## Source Documents

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-J02
- [AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit) — AI-03
- [PRD — Aria AI MVP v1.0](https://docs.google.com/document/d/1zObOV8H1Moj2qcgAHjRqy5gVzS5ipg-CS__4CFgM9Gg/edit) — FR-06
- [Detailed Data Dictionary v1.0](https://docs.google.com/document/d/1TIZ96m-VvtdR3-_QtnsC5sK_maqfi_aMcUhj9xTDCaQ/edit) — Gap/Job persistence baseline
- [ADR-036 — Gap Detection Foundation](../../adr/ADR-036-gap-detection-foundation.md)
- Owner-approved J02-A split and refinements dated 2026-09-09.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
| --- | --- | --- | --- |
| REQ-4901 | J02-A owner contract: exact dual revision snapshot | `packages/backend-application/src/aria_backend_application/gap_detection.py`; `apps/api/app/modules/gaps/infrastructure/detection_repository.py` | TC-4901 |
| REQ-4902 | J02-A owner contract: exact candidate and resolution vocabulary | `gap_detection.py`; `apps/api/migrations/versions/0015_gap_detection.py` | TC-4902 |
| REQ-4903 | J02-A owner contract: provenance and affected-Requirement validation | `gap_detection.py`; `detection_repository.py` | TC-4903 |
| REQ-4904 | J02-A owner contract: deterministic exact duplicate rejection | `gap_detection.py` | TC-4904 |
| REQ-4905 | J02-A owner contract: atomic Gap/link/Job-result persistence | `0015_gap_detection.py`; `detection_repository.py` | TC-4905 |
| REQ-4906 | J02-A owner contract: terminal replay including zero-Gap result | `gap_detection.py`; `detection_repository.py` | TC-4906 |
| REQ-4907 | AI Workflow and G05: metered provider-neutral execution | `gap_detection.py`; existing `AIExecutionPort` and `UsageLedger` | TC-4907 |
| REQ-4908 | J02-A/J02-B boundary: Critical evaluator port only | `gap_detection.py`; `docs/adr/ADR-036-gap-detection-foundation.md` | TC-4908 |
| REQ-4909 | J02-A safe structured logging | `gap_detection.py`; `packages/observability/src/aria_observability/logging.py` | TC-4909 |
| REQ-4910 | AGENTS quality/documentation gates | This record and test report | TC-4910 |

## Assumptions and Clarifications

- The 2026-09-09 owner contract is authoritative for J02-A and explicitly leaves J02-B blocked.
- The existing private `jobs.payload_ref` is the approved Job metadata container; J02-A records
  only the explicitly approved `gap_count` result metadata key and preserves all existing keys.
- J01 Gap creation remains valid, so the three J02 generation fields are nullable at the storage
  boundary while every AI-generated Gap is required by the J02-A Application contract to populate
  all three.

**Unapproved assumptions:** None

## Changes

- Added migration `0015_gap_detection`: three nullable J02 generation fields, canonical resolution
  check, same-tenant Job FK, tenant-first replay index, and normalized
  `gap_requirement_links` with restrictive composite FKs, RLS and revoked Data API grants.
- Added a database trigger that rejects Gap/Requirement links from different Context snapshots.
- Added provider-neutral Snapshot, Candidate, repair, Critical-rule and persistence ports plus the
  `DetectGapsUseCase`. Empty output is successful; exact duplicates reject the whole Batch.
- Added SQLAlchemy snapshot/repository adapters with dual exact-set locking, ready-provenance
  revalidation, atomic Gap/link/Job-result commit and terminal replay verification.
- Preserved existing Job metadata while adding the approved `gap_count` key. Same-Job concurrent
  deliveries serialize on the Job row so only one Batch commits and the other resolves replay.
- Added safe Gap detection observability fields and explicit negative tests for customer/model
  content.
- Updated the developer data-model and migration mirrors plus ADR index. No API or UI was added.

## Architecture and Design Decisions

See ADR-036. No concrete Critical rule, checklist content, Provider or Queue behavior is selected.

## Structure Preservation

- Domain/Application remains framework-neutral; SQLAlchemy and PostgreSQL locking stay in the API
  Infrastructure adapter.
- Existing modular-monolith modules and Alembic chain are extended, not rewritten.
- Affected Requirements are relational, not JSONB, and all indexes/FKs retain the Tenant anchor.
- No public API, UI, Provider SDK, Worker task, Queue contract or deployable service was added.
- J01 rows remain representable because J02-only storage fields are nullable; generated writes are
  complete by construction in the J02 Application command.

## Senior Review

**Status:** PASS for S1-J02-A.

- Confirmed dual revision vectors detect insert, update and predicate-exit races for both Context
  Items and Requirements; Project type is compared again under lock.
- Confirmed replay is tenant-scoped, validates authoritative `gap_count` against persisted rows,
  supports zero rows, preserves existing Job metadata, and creates no AI/Usage/write side effect.
- Confirmed exact duplicate identity canonicalizes both Source References and affected Requirement
  IDs without introducing fuzzy/semantic behavior.
- Confirmed model-proposed Critical severity is counted but cannot become authoritative unless the
  injected deterministic evaluator returns a match; J02-A ships no evaluator policy.
- Confirmed candidate provenance is both exact-snapshot checked in Application and revalidated
  against same-tenant ready Source Versions in Infrastructure before AI execution.
- Confirmed Gap, links and terminal Job result commit together; DB constraints also reject
  cross-tenant Jobs/links and cross-snapshot Requirements.
- Review found and fixed: missing duplicate telemetry on successful repair, a concurrent-delivery
  replay race, missing revalidation of corrupted persisted provenance, and insufficient DB tests
  for resolution vocabulary/cross-tenant Job linkage.
- No unresolved High/Medium defect, leaked content, hidden Critical policy or structural violation
  remains in J02-A.

## Verification

- Contract/CI: 130/130 PASS; focused Gap contracts: 8/8 PASS.
- Focused J02 Application/PostgreSQL: 17/17 PASS before final added cases; final full API:
  392/392 PASS with PostgreSQL integration enabled.
- Eval: 24/24 PASS; Web: 26/26 PASS; Worker: 57/57 PASS.
- Full lint, typecheck and production build: PASS.
- Final repository `npm test`, `npm run validate`, secret scan and diff check: see linked report.

## Remaining Risks

- S1-J02-B remains blocked until the versioned Completion Checklist and Critical Rule Pack are
  approved. Consequently full S1-J02 is not done and Gap Detection is not Production-ready.
- Concrete Provider/Worker/Queue wiring and real model-quality evaluation remain deferred.
- The short final transaction uses Job/Project row locks plus SHARE table locks. This is correct for
  Sprint 1 but requires contention measurement before scale.
- Local PostgreSQL 16 proves migrations and constraints; hosted Supabase migration application is
  outside this Increment.
