import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { classifyControlledRequest, validateSetup } from "../preview-publication/browser-proof.mjs";

const setup = { artifact_version_id: "00000000-0000-0000-0000-000000000001", pages:["index.html","services/design/index.html"],profile_parent:"C:/owned/.tmp/preview-joined-"+"a".repeat(32)+"/case" };

test("0102 Browser setup rejects unrelated profiles and malformed input before launch",()=>{
  assert.deepEqual(validateSetup(setup).pages,setup.pages);
  for (const invalid of [{...setup,token:"synthetic-secret"},{...setup,profile_parent:"C:/Users/browser"},{...setup,pages:["../index.html"]},{...setup,pages:["index.html","index.html"]},{...setup,artifact_version_id:"other"}]) assert.throws(()=>validateSetup(invalid),/CONTROLLED_BROWSER_FAILED/);
});

test("0102 request interception cannot mask the armed native non-network download probe",()=>{
  const origins=new Set(["http://core.aria-core.test:1234"]);
  assert.equal(classifyControlledRequest("http://core.aria-core.test:1234/",origins,false),"approved_site");
  assert.equal(classifyControlledRequest("data:text/plain,synthetic",origins,false),"unexpected");
  assert.equal(classifyControlledRequest("data:text/plain,synthetic",origins,true),"local_probe");
  for(const url of ["data:text/plain,other","https://outside.test/","http://core.aria-core.test:1234.evil.test/","about:blank"]) assert.equal(classifyControlledRequest(url,origins,true),"unexpected");
});

test("0102 Browser proof keeps capabilities out of process arguments and saved diagnostics", async()=>{
  const source=await readFile(new URL("../preview-publication/browser-proof.mjs",import.meta.url),"utf8");
  assert.match(source,/stdio: "ignore", windowsHide: true/);
  assert.match(source,/--no-proxy-server/);
  assert.match(source,/--disable-extensions/);
  assert.match(source,/sandbox="allow-scripts" referrerpolicy="no-referrer"/);
  assert.doesNotMatch(source,/allow-same-origin|allow-forms|allow-popups|allow-downloads|unsafe-inline|unsafe-eval|Network\.setExtraHTTPHeaders/);
  assert.doesNotMatch(source,/console\.(?:log|error)|writeFile|captureScreenshot|Tracing\.start|entry\.text/);
  assert.match(source,/Fetch\.continueRequest/);
  assert.match(source,/allowedOrigins\.has/);
  assert.match(source,/rm\(profile/);
});
