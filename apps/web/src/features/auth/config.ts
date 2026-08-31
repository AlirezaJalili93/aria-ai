class AuthConfigurationError extends Error {
  constructor() {
    super("Authentication runtime configuration is unavailable")
    this.name = "AuthConfigurationError"
  }
}

function requiredUrl(value: string | undefined): string {
  if (!value) throw new AuthConfigurationError()
  try {
    return new URL(value).toString()
  } catch {
    throw new AuthConfigurationError()
  }
}

export function getSupabaseConfig(): { url: string; publishableKey: string } {
  const publishableKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY
  if (!publishableKey) throw new AuthConfigurationError()
  return {
    url: requiredUrl(process.env.NEXT_PUBLIC_SUPABASE_URL),
    publishableKey
  }
}

export function getApiBaseUrl(): string {
  return requiredUrl(process.env.NEXT_PUBLIC_API_BASE_URL)
}

export function getPublicAppUrl(): string {
  return requiredUrl(process.env.PUBLIC_APP_URL)
}

export function isAuthConfigurationError(error: unknown): boolean {
  return error instanceof AuthConfigurationError
}
