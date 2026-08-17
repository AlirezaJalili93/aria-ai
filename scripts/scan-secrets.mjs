import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { scanPublishableFiles } from "./lib/secret-scan.mjs";

const outputIndex = process.argv.indexOf("--output");
const outputPath = outputIndex >= 0 ? process.argv[outputIndex + 1] : undefined;

if (outputIndex >= 0 && !outputPath) {
  console.error("FAIL  --output requires a file path");
  process.exit(2);
}

try {
  const result = scanPublishableFiles(process.cwd());
  const report = {
    filesScanned: result.filesScanned,
    findings: result.findings,
    status: result.findings.length === 0 ? "PASS" : "FAIL"
  };

  if (outputPath) {
    await mkdir(path.dirname(path.resolve(outputPath)), { recursive: true });
    await writeFile(path.resolve(outputPath), `${JSON.stringify(report, null, 2)}\n`, "utf8");
  }

  if (result.findings.length === 0) {
    console.log(`PASS  Secret scan inspected ${result.filesScanned} publishable text files`);
  } else {
    for (const finding of result.findings) {
      console.error(`FAIL  ${finding.path}:${finding.line} (${finding.detector})`);
    }
    console.error(`Secret scan found ${result.findings.length} potential secret(s).`);
    process.exitCode = 1;
  }
} catch (error) {
  console.error(`FAIL  Secret scan could not run: ${error.message}`);
  process.exitCode = 1;
}
