# 0097 Controlled Generation Exportability

`run-clean-room.mjs` creates three disposable Next.js static-export candidates outside the
repository. It packs `@aria/generation-renderer` and `@aria/design-tokens`, installs from local
tarballs plus pinned public dependencies, audits, builds, serves and scans each candidate, writes
bounded evidence, then removes the complete temporary root.

Run from the repository root:

```powershell
npm run test:generation-exportability
npm run proof:generation-exportability
```

The proof contains synthetic fixtures only. It is not a production Export Service or Preview host.
