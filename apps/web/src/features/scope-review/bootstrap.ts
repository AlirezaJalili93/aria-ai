const PUBLIC_TOKEN_LENGTH = 43

type BrowserLocation = Pick<Location, "hash">
type BrowserHistory = Pick<History, "replaceState" | "state">

export function consumeScopeReviewToken(
  location: BrowserLocation,
  history: BrowserHistory
): string | null {
  const fragment = location.hash.startsWith("#") ? location.hash.slice(1) : location.hash
  const parameters = new URLSearchParams(fragment)
  const tokenValues = parameters.getAll("token")
  const token = parameters.size === 1 && tokenValues.length === 1 ? tokenValues[0] : null

  history.replaceState(history.state, "", "/scope-review")
  return token !== null && isCanonicalPublicToken(token) ? token : null
}

function isCanonicalPublicToken(token: string): boolean {
  if (token.length !== PUBLIC_TOKEN_LENGTH || !/^[A-Za-z0-9_-]+$/.test(token)) return false
  try {
    const encoded = token.replaceAll("-", "+").replaceAll("_", "/") + "="
    const bytes = Uint8Array.from(atob(encoded), (character) => character.charCodeAt(0))
    if (bytes.length !== 32) return false
    const canonical = btoa(String.fromCharCode(...bytes))
      .replaceAll("+", "-")
      .replaceAll("/", "_")
      .replace(/=+$/, "")
    return canonical === token
  } catch {
    return false
  }
}
