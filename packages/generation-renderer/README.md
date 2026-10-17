# Aria Generation Renderer

`@aria/generation-renderer` is the framework-independent React rendering boundary for
`generation_ast_schema_v1`. It accepts only the Application-enriched canonical AST; Provider
candidate output is rejected.

Consumers import `@aria/design-tokens/tokens.css` followed by
`@aria/generation-renderer/styles.css`. Assets are resolved only through an `AssetResolver`; this
package never turns an Asset UUID or remote URL directly into an image source.

The Renderer deliberately uses a native `img` element with resolver-supplied dimensions because it
must remain portable outside Next.js; its package-local ESLint config disables only the two
Next.js-specific page/image rules. React, TypeScript and accessibility rules remain enabled.

The package has no Next.js, Backend, Database, Storage or Provider dependency. Preview isolation,
Artifact persistence and Export remain separate increments.
