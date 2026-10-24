import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(new URL(path, import.meta.url), "utf8");

test("Context review exposes canonical tabs, provenance and safe review commands", async () => {
  const review = await read("../src/features/context/context-review.tsx");
  const api = await read("../src/features/context/api.ts");
  const actions = await read("../src/features/context/actions.ts");
  const styles = await read("../src/app/globals.css");
  const combined = `${review}\n${api}\n${actions}`;

  for (const type of ["fact", "assumption", "decision", "constraint", "reference", "unknown"]) {
    assert.match(combined, new RegExp(`\\"${type}\\"`));
  }
  assert.match(review, /role="tablist"/);
  assert.match(review, /source_refs\.length/);
  assert.match(review, /expected_updated_at/);
  assert.ok(actions.includes("revalidatePath(`/projects/${projectId}/context`)"));
  assert.match(styles, /context-item-card--assumption/);
  assert.match(styles, /min-block-size: var\(--button-height\)/);
  assert.doesNotMatch(combined, /deleteContextItem|regenerateContextItem|context-structuring/);
});
