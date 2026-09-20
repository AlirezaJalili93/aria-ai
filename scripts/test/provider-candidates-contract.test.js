import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";

const root = resolve(import.meta.dirname, "../..");
const read = (path) => readFileSync(resolve(root, path), "utf8");

test("0068 pins only the approved official provider SDKs and candidates", () => {
  const project = read("apps/worker/pyproject.toml");
  const example = read(".env.example");

  assert.match(project, /openai==3\.16\.2/);
  assert.match(project, /google-genai==2\.24\.0/);
  assert.match(example, /OPENAI_API_KEY=\s*$/m);
  assert.match(example, /OPENAI_MODEL=gpt-5\.6-terra/);
  assert.match(example, /GEMINI_API_KEY=\s*$/m);
  assert.match(example, /GEMINI_MODEL=gemini-3\.8-flash/);
});

test("OpenAI candidate disables tools, SDK retry and implicit cache writes", () => {
  const adapter = read("apps/worker/app/infrastructure/ai/openai_responses.py");

  assert.match(adapter, /max_retries=0/);
  assert.match(adapter, /Timeout\(60\.0, connect=5\.0/);
  assert.match(adapter, /tools=\[\]/);
  assert.match(adapter, /prompt_cache_options=.*explicit/s);
  assert.match(adapter, /cache_write_tokens/);
  assert.match(adapter, /UnsupportedProviderAccountingError/);
  assert.doesNotMatch(adapter, /web_search|file_search|function_call/);
});

test("Gemini candidate keeps context caching and tools disabled", () => {
  const adapter = read("apps/worker/app/infrastructure/ai/gemini_generate_content.py");

  assert.match(adapter, /gemini-3\.8-flash/);
  assert.match(adapter, /candidates_token_count/);
  assert.match(adapter, /thoughts_token_count/);
  assert.match(adapter, /AutomaticFunctionCallingConfig\(disable=True\)/);
  assert.match(adapter, /HttpRetryOptions\(attempts=1\)/);
  assert.match(adapter, /Timeout\(60\.0, connect=5\.0/);
  assert.doesNotMatch(adapter, /cached_content\s*=/);
  assert.doesNotMatch(adapter, /google_search|function_declarations/);
});

test("candidate execution resolves and retains price before invoking an adapter", () => {
  const execution = read("apps/worker/app/application/provider_execution.py");

  assert.match(execution, /await catalog\.resolve/);
  assert.match(execution, /await candidate\.adapter\.execute/);
  assert.match(execution, /price: ProviderPriceVersion/);
});

test("0068 does not promote a primary provider or fallback", () => {
  const adr = read("docs/adr/ADR-055-provider-adapter-candidates.md");

  assert.match(adr, /Primary:\s*none/i);
  assert.match(adr, /Fallback:\s*none/i);
  assert.match(adr, /synthetic/i);
  assert.match(adr, /cache_write_tokens.*zero/is);
});
