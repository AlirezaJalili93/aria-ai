# Aria Web

Next.js App Router and TypeScript Strict presentation boundary.

- UI is RTL-first and imports the canonical `@aria/design-tokens` package.
- Product feature code stays under `src/features` when its story is implemented.
- Web code may call the typed HTTP client but cannot access databases, queues, storage credentials, or AI providers directly.

Commands are run from the repository root through npm workspaces.
