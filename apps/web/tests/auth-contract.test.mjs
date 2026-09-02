import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(new URL(path, import.meta.url), "utf8");

test("Email/Password is the only S1-B05 authentication method", async () => {
  const login = await read("../src/app/auth/login/page.tsx");
  const signup = await read("../src/app/auth/signup/page.tsx");
  const form = await read("../src/features/auth/auth-form.tsx");
  const actions = await read("../src/features/auth/actions.ts");
  const combined = `${login}\n${signup}\n${form}\n${actions}`;

  assert.match(actions, /signInWithPassword/);
  assert.match(actions, /signUp/);
  assert.match(combined, /type="email"/);
  assert.match(combined, /type="password"/);
  assert.doesNotMatch(combined, /magic\s*link|signInWithOtp|recovery|forgot|terms_version|privacy_version/i);
});

test("Signup stops at the mandatory email confirmation state", async () => {
  const signup = await read("../src/app/auth/signup/page.tsx");
  const actions = await read("../src/features/auth/actions.ts");

  assert.match(signup, /ایمیل تأیید ارسال شد/);
  assert.match(actions, /emailRedirectTo/);
  assert.doesNotMatch(actions, /signup[\s\S]{0,1200}redirect\(["']\/projects/);
});

test("Login and callback bootstrap before the projects redirect", async () => {
  const actions = await read("../src/features/auth/actions.ts");
  const callback = await read("../src/app/auth/callback/route.ts");

  assert.match(actions, /signInWithPassword[\s\S]*bootstrapSession[\s\S]*redirect\(["']\/projects["']\)/);
  assert.match(callback, /exchangeCodeForSession|verifyOtp/);
  assert.match(callback, /bootstrapSession[\s\S]*pathname\s*=\s*["']\/projects["']/);
  assert.match(callback, /searchParams\.delete\(["']token_hash["']\)/);
  assert.match(callback, /searchParams\.delete\(["']code["']\)/);
  assert.match(callback, /Cache-Control["'],\s*["']private,[^"']*no-store/);
});

test("Auth failures and logout expose the approved safe event vocabulary", async () => {
  const logging = await read("../src/features/auth/logging.ts");
  const actions = await read("../src/features/auth/actions.ts");
  const callback = await read("../src/app/auth/callback/route.ts");
  const logout = await read("../src/app/auth/logout/route.ts");
  const combined = `${logging}\n${actions}\n${callback}\n${logout}`;

  for (const event of [
    "auth.signup_started",
    "auth.signup_completed",
    "auth.signup_failed",
    "auth.login_succeeded",
    "auth.login_failed",
    "auth.callback_succeeded",
    "auth.callback_failed",
    "auth.logout_completed"
  ]) {
    assert.match(combined, new RegExp(event.replaceAll(".", "\\.")));
  }
  assert.doesNotMatch(logging, /email|password|access_token|refresh_token|token_hash|raw_sub/i);
  for (const field of [
    "schema_version",
    "service",
    "environment",
    "app_version",
    "release_commit_sha",
    "request_id",
    "correlation_id"
  ]) {
    assert.match(logging, new RegExp(field));
  }
});

test("Callback keeps safe internal failure classes distinct", async () => {
  const callback = await read("../src/app/auth/callback/route.ts");

  for (const reason of [
    "invalid_or_expired",
    "configuration_unavailable",
    "rate_limited",
    "auth_provider_unavailable",
    "auth_required",
    "bootstrap_unavailable",
    "unexpected_failure"
  ]) {
    assert.match(callback, new RegExp(reason));
  }
  assert.match(callback, /error instanceof BootstrapRequestError/);
  assert.match(callback, /callbackProviderFailureReason\(result\.error\.status\)/);
});

test("framework request logging excludes the credential-bearing callback URL", async () => {
  const nextConfig = await read("../next.config.ts");

  assert.match(nextConfig, /incomingRequests[\s\S]*ignore[\s\S]*auth\\\/callback/);
});

test("Protected projects route and SSR proxy verify claims", async () => {
  const projects = await read("../src/app/projects/page.tsx");
  const projectApi = await read("../src/features/projects/api.ts");
  const proxy = await read("../src/features/auth/supabase/proxy.ts");

  assert.match(projects, /resolveProjectAccess\(\)/);
  assert.match(projectApi, /getClaims\(\)[\s\S]*getSession\(\)/);
  assert.match(projects, /redirect\(["']\/auth\/login["']\)/);
  assert.doesNotMatch(projects, /\/onboarding/);
  assert.doesNotMatch(projects, /bootstrapSession|getSession\(\)/);
  assert.doesNotMatch(projectApi, /bootstrapSession/);
  assert.match(proxy, /getClaims\(\)/);
});

test("Auth UI keeps semantic labels, status announcements and LTR email inputs", async () => {
  const login = await read("../src/app/auth/login/page.tsx");
  const signup = await read("../src/app/auth/signup/page.tsx");
  const form = await read("../src/features/auth/auth-form.tsx");
  const styles = await read("../src/app/globals.css");
  const combined = `${login}\n${signup}\n${form}`;

  assert.match(combined, /<label[^>]*htmlFor=/);
  assert.match(combined, /aria-live="polite"|role="alert"/);
  assert.match(styles, /direction:\s*ltr/);
  assert.match(styles, /min-block-size:\s*var\(--(?:button|field)-height\)/);
  assert.doesNotMatch(styles, /#[0-9a-f]{3,8}\b/i);
});
