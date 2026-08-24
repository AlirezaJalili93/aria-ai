# Infrastructure adapters

Database, auth, storage, queue, AI and analytics adapters are added only with their approved contract and contract tests.

The Auth adapter verifies Supabase-issued access tokens against the configured public JWKS. It is
the only application source location allowed to import PyJWT; Application receives only the
provider-neutral `AccessTokenVerifier` contract and `AuthenticatedIdentity` result.
