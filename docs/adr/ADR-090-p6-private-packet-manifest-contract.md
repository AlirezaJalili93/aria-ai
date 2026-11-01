# ADR-090 P6 — Private Packet Manifest Contract

**Revision:** P6 r1, 2026-11-01.
**Current contract status:** APPROVED / FROZEN AT CONTRACT LEVEL — owner decision, 2026-11-01.
**Execution status:** NOT IMPLEMENTED / NOT RUN; implementation and execution remain NO-GO.
Section 8 records the exact approval; earlier proposal labels in r1 below are review history,
not the current contract status. Normative sections 2..7 are unchanged.
**Current authority:** owner approved the complete exact P6 r1 contract, including its fields,
names and paths. The prior direction-only decision did not approve the parent's v0.19 text;
the later exact P6 Freeze is recorded independently in section 8.
**Scope:** Local/Synthetic documentation only. Runtime, SQL execution, Migration, Browser Proof,
Hosted/customer use, Commit and Push remain NO-GO. P7 exact drafting is now authorized, not Frozen.

## 1. Sources and precedence

The current owner decision, frozen [P4](ADR-090-controlled-preview-workspace-contract.md)
(P4.1..P4.5/R1..R4), frozen [P5 r3.1](ADR-090-p5-sql-contract.md), and
[ADR-089](ADR-089-local-preview-publication-and-capability.md) define the boundaries.
Canonical source links/review date **2026-10-17** remain in the parent ADR; no fresh Drive
review or synchronization is claimed. Repository source inspection: **2026-11-01**,
`packages/backend-application/src/aria_backend_application/preview_delivery.py` and the existing
Worker publishing/storage/access adapters. Those sources describe 0102, not permission to extend it.

All exact P6 choices below are proposals for source review. Existing P4/P5 requirements are
inherited, not reopened. No executable JSON Schema, SQL, fixture or implementation accompanies r1.

## 2. Closed shape and value rules

Proposed Manifest identity: `preview_bootstrap_manifest/v1`. All listed fields are REQUIRED;
objects are closed at every level. Additional/missing/duplicate keys, nulls, coercion, aliases
and unknown versions are rejected. No optional/default fields or extensible metadata bag exist.

| Field | Exact proposed type / constraint |
|---|---|
| `manifest_version` | String literal `preview_bootstrap_manifest/v1` |
| `representation_id` | UUID string; exact stored Representation |
| `source` | Closed object containing exactly the seven fields below |
| `source.account_id`, `source.project_id`, `source.artifact_id`, `source.artifact_version_id` | UUID strings; exact bound database graph |
| `source.version_no` | Integer >= 1; exact bound ArtifactVersion number |
| `source.artifact_hash` | SHA-256 digest of the exact source `artifact_manifest/v1` bytes, matching stored `source_hash` |
| `source.manifest_version` | String literal `artifact_manifest/v1` |
| `contracts` | Closed object containing exactly the three fields below |
| `contracts.generation_ast_schema_version` | String literal `generation_ast_schema/v1` |
| `contracts.transformer_version` | String literal `preview_bootstrap_transformer_v1` |
| `contracts.delivery_policy_version` | String literal `preview_bootstrap_delivery_policy_v1` |
| `pages` | Nonempty array of unique canonical path strings, in exact source `canonical_ast.pages` order |
| `packet` | Closed object containing exactly `path`, `media_type`, `size_bytes`, `sha256` |
| `packet.path` | String literal `packet.html`; private storage suffix, NOT a browser route |
| `packet.media_type` | String literal `text/html; charset=utf-8` |
| `packet.size_bytes` | Integer in 1..8,388,608; exact final response-body byte count |
| `packet.sha256` | SHA-256 digest of the exact final packet bytes |
| `csp` | Closed object containing exactly `script_sha256`, `style_sha256` |
| `csp.script_sha256`, `csp.style_sha256` | Canonical CSP SHA-256 hash-source values defined below |

UUID strings use lowercase hyphenated 36-character notation and must equal the stored identity;
syntactic UUID validity alone grants nothing. Integers exclude booleans, fractions, exponent
notation and numeric strings. Every digest outside `csp` uses `sha256:` plus 64 lowercase hex
digits. CSP values use `sha256-` plus standard, padded Base64 of exactly 32 digest bytes;
strict decode/re-encode equality is required. Quotes delimiting a CSP source are not stored.

Each page path must pass the existing canonical AST path contract, exist in that same source,
and occur once. No sorting, normalization, root-page insertion or latest-page lookup is allowed.
`pages[0]` is the initial page; no redundant mutable `initial_page` field exists. Page titles,
canonical Page/Section IDs and content are not duplicated in the Manifest. P4 preserves them in
the packet, with its combined DOM/IDREF validation. Source AST limits remain unchanged.

## 3. Private namespace and immutability

Proposed exact server-generated keys, with UUID notation from section 2:

```text
preview-bootstrap/{account_id}/{project_id}/{artifact_version_id}/{representation_id}/packet.html
preview-bootstrap/{account_id}/{project_id}/{artifact_version_id}/{representation_id}/packet-manifest.json
```

The second key is the proposed `manifest_ref`; its exact Manifest digest is `manifest_hash` on
the Representation. Derive both keys from validated binding, never a request path, Manifest
override or caller-provided prefix. Reject a mismatched reference; do not normalize traversal,
follow links/junctions or use directory/other-version fallback. Storage remains private: no
anonymous read/list, public asset route or URL is created. These new keys do not alter 0102 keys.

Ready bytes and reference/hash are immutable. Creation is create-or-verify, never overwrite;
read back and verify the packet, then Manifest, before P7 may finalize. Packet/Manifest are
Representation-scoped, reusable across Publications, and contain no injected capability,
Publication access state, expiry, Host, session, Cookie or credential. No token/token_hash,
Publication ID, raw prompt/response or copied source-file inventory is a Manifest field.
This proposal creates no cleanup policy or permission to delete either private object.

## 4. Three authority boundaries and non-circular hashes

1. **Source/profile authority:** during preparation, verify the exact database-bound source
   Manifest, every declared file and canonical AST under P4 before transformation. Ordered pages
   come only from that AST. Reviewed Application-owned script and verified CSS provenance under
   the frozen profile authorize execution/style; a Manifest claim cannot authorize new inputs.
2. **Private metadata integrity:** the stored, trusted Representation `manifest_hash` pins the
   exact serialized Manifest. A hash read from that same Manifest or supplied by a client is not
   a substitute. Verify this outer hash before accepting metadata; then compare all identities
   and fixed versions against the database/profile, not against each other alone.
3. **Packet integrity/CSP:** verify exact packet size/hash and P4 eligibility. Hash each exact
   final inline script/style UTF-8 text, LF-only, excluding tags, after provenance validation.
   Exactly one authorized script and one authorized style must match both expected content and
   their Manifest CSP hashes. An extra/modified resource with a matching claimed hash is denied.

Compute in this acyclic order: verified source/profile -> final P4 packet bytes -> inline hashes
and whole-packet size/hash -> canonical Manifest bytes -> outer Manifest hash stored by P7.
Do not inject this Manifest, its hash or packet-integrity metadata into packet bytes. CSP remains
an HTTP header constructed from the fixed P4 template and verified inline hashes; the exact
approved Core origin comes from trusted delivery configuration, never this Manifest. No stored
full CSP, arbitrary source list, nonce or origin override is accepted. Headers are not hashed as
part of `packet.sha256`. Source, packet and Manifest digests are distinct; no self-hash field exists.

The script/serialization implementation and approved CSS inputs are bound to the reviewed
transformer/policy pair, not to loose caller-selected script versions. P4 requires version/hash
review on changes. Actual script/style bytes, their hashes and serialization implementation
are still unreviewed; this proposal supplies neither placeholder authorization nor runtime trust.

## 5. Canonical Manifest and response bytes

Propose the existing application's canonical-JSON convention for P6 only: strict UTF-8, no BOM,
no trailing newline, recursively sorted object keys, no insignificant whitespace, unescaped
non-ASCII characters, arrays in specified order. Precisely use the byte representation of
Python `json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
allow_nan=False).encode("utf-8")` on a validated value. This is not a claim of RFC 8785 compliance.
Reject duplicate keys, invalid UTF-8, surrogate code points and noncanonical input bytes by
strict parsing plus exact reserialization equality; do not silently canonicalize stored input.

Final HTML is P4's reviewed UTF-8/LF-only serialization, without BOM. Count/hash all final bytes,
including all pages and inline resources; not code points, compressed size or source size.
8,388,608 bytes is allowed; 8,388,609 is not. No truncation, resource/page removal, normalization
after hashing, response rewriting or compression is permitted. Identity-only means no response
Content-Encoding header, not a new literal `Content-Encoding: identity` header. The same verified
immutable byte sequence must be sent; Content-Length equals its measured length.

## 6. Before consumption, not after

Approved Host/Origin/P2/P3 guards precede P5 Preflight. Preflight's ten private fields remain
unchanged. P5 enforces the fixed database profile; compare its returned identities and derived
`manifest_ref` with the Manifest's exact binding and fixed versions. Read Manifest once, verify its
stored outer hash, closed shape/canonical encoding and exact binding. Then read the sole packet
into the immutable response buffer; verify size/hash, inline hashes and all P4 closed structural,
page/IDREF, SVG, CSS, navigation/resource restrictions, including inactive templates.

At delivery the pinned Manifest is expected metadata from trusted preparation, not independent
proof of source provenance or permission to run arbitrary code. Its page inventory must match
the validated packet; its script must still match the independently reviewed fixed Application
source. CSS provenance was verified before publishing, and its final bytes remain pinned by the
trusted Manifest hash and checked against the closed P4 style rules. No rendering/repair, source
mutation, latest-state selection or request-time regeneration is introduced.

All preparation/storage/integrity failures stop BEFORE Consume, disclose no packet and consume
nothing. Public response remains `404 RESOURCE_NOT_FOUND`; excess packet size has only the
already-approved internal `PREVIEW_PACKET_TOO_LARGE` reason, with no size/path/binding leak.
This does not change P3's earlier request-size/encoding/structure errors or invent new reason codes.
Do not include packet/Manifest bodies, private references/hashes, capabilities or raw exception
context in logs, metrics, traces, analytics or public errors; diagnostics use approved bounded
outcome/reason codes only. The Manifest is private validation metadata, not an operational log.

Only fully verified bytes may reach P5 Consume with the original hash-resolved Publication,
Representation, ArtifactVersion and Manifest hash. Revalidation/unique consumption and expiry
after lock wait remain exactly P5. Send no preview bytes before confirmed commit. Failed or
ambiguous commit acknowledgment sends none, grants no automatic retry/reissue and cannot erase
consumption. No storage read, transformation or final body mutation is deferred until after commit.
Network failure after commit loses the response without restoring capability. D6 still disclaims
live revocation of delivered bytes. Publishing/recovery may never clear or bypass the ledger.

## 7. Review traceability and future evidence

| Requirement / source | Contract | Required future evidence (ALL NOT RUN) |
|---|---|---|
| REQ-10329 — owner P6 exact contract first; P4/P5 unchanged | Sections 1..3 | Wrong/extra/missing/version/type fields; wrong tenant/project/source/profile/reference denied; 0102 unchanged |
| REQ-10330 — owner final-byte binding/order/cap; P4.R1..R4 | Sections 2,4,5 | Source page order differs from lexical order; packet/Manifest/inline hashes distinct; changed bytes plus self-claimed hash denied; exact cap boundaries |
| REQ-10331 — owner validation authority/no circular hash | Sections 4..6 | Canonical/duplicate-key/UTF-8 failures; mismatched DB hash; source/script/CSS provenance rejection; template/resource/IDREF validation; no consumption on failure |
| REQ-10332 — owner no publishing/recovery reissue; P5/D6 | Section 6 | Concurrent consume/revoke; commit failure/ambiguity and lost response; same representation under separate Publications; consumed capability stays consumed |

These observations refine existing TC-103M01..06 and TC-103D01..12; they do not replace the 17
P5 SQL scenarios + 7 subcases or browser matrix. All P6/P7 execution remains NOT RUN. No new
test implementation or completed development increment exists. Unapproved design decisions are
the exact P6 identity, shape, namespace and serialization in this r1 proposal; none is implemented.
P7 exact signatures/permissions/states/idempotency/revoke/recovery are intentionally not drafted
before independent P6 review. Full ADR Freeze WAIT; implementation/execution NO-GO.

## 8. Owner exact-contract Freeze — 2026-11-01

The owner reviewed the complete P6 r1 text dated 2026-11-01 and explicitly declared
**APPROVED / FROZEN — CONTRACT LEVEL**, including Manifest identity/fields, serialization,
private paths, authority/hash boundaries, source order and validation before consumption.
The original review snapshot was 176 lines / 13,295 bytes with raw SHA-256
`EB3494A2164B3E38A7DAE8DE498786FFE8B18E97B705A07C2B4065D9A13FB614`.
This approval/status addition changes the whole-file hash, not the r1 contract substance.
Sections 2..7 retain normalized-LF SHA-256 (excluding final newlines)
`B13C75B97982DA1CD69B8FB014BAB7C1E090F67C3CFB53A964852125377C4AFE`.

All prior phrases calling these exact choices unapproved/proposed are superseded solely as
contract status; none authorizes code, SQL, Migration, new Browser Proof or actual hash/script/CSS
implementation. Any substantive change requires a reviewed revision. P4 and P5 stay unchanged.
P7 exact contract design is now authorized and PENDING REVIEW; full ADR Freeze WAIT.
Every dedicated P6 execution case remains NOT RUN. Hosted/customer use and Commit/Push remain
NO-GO. No remote/Drive approval or independent execution evidence is claimed by this record.
