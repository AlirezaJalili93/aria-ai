import { readFile } from "node:fs/promises";
import { assertCanonicalGenerationAst } from "../../packages/generation-renderer/dist/index.js";

// Fixed validation only: no rendering, compilation, provider invocation or diagnostics.
const [inputPath] = process.argv.slice(2);
if (!inputPath || process.argv.length !== 3) process.exit(1);
try {
  assertCanonicalGenerationAst(JSON.parse(await readFile(inputPath, "utf8")));
} catch {
  process.exit(1);
}
