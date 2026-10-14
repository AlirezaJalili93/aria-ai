// Test-only controlled Browser proof. Capability/config enter captured stdin, never argv/env/file.
import { spawn } from "node:child_process";
import { access, mkdir, rm } from "node:fs/promises";
import { createServer } from "node:http";
import { createServer as tcpServer } from "node:net";
import { createInterface } from "node:readline";
import path from "node:path";
import { randomUUID } from "node:crypto";
import { fileURLToPath } from "node:url";

const CORE = "core.aria-core.test";
const ATTACKER = "attacker.aria-other.test";
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const fixedFailure = () => new Error("CONTROLLED_BROWSER_FAILED");

export function validateSetup(value) {
  if (!value || Object.keys(value).sort().join(",") !== "artifact_version_id,pages,profile_parent") throw fixedFailure();
  if (!/^[0-9a-f-]{36}$/.test(value.artifact_version_id) || !Array.isArray(value.pages) || !value.pages.length) throw fixedFailure();
  if (!value.pages.every((p) => typeof p === "string" && /^(?:[A-Za-z0-9_-]+\/)*index\.html$/.test(p))) throw fixedFailure();
  if (!value.pages.includes("index.html") || new Set(value.pages).size !== value.pages.length) throw fixedFailure();
  const root = path.resolve(value.profile_parent);
  // Profile lives only inside an owned joined-test directory, never a user browser profile.
  if (!/[/\\]\.tmp[/\\]preview-joined-[0-9a-f]{32}[/\\]/i.test(root + path.sep)) throw fixedFailure();
  return { ...value, profile_parent: root };
}

export function classifyControlledRequest(url, allowedOrigins, localProbeArmed) {
  // Only this exact harness-owned non-network probe is permitted, after it is armed.
  // Let native sandbox/download enforcement decide; interception must not mask that test.
  if (localProbeArmed && url === "data:text/plain,synthetic") return "local_probe";
  try { if (allowedOrigins.has(new URL(url).origin)) return "approved_site"; } catch { /* deny */ }
  return "unexpected";
}

class Protocol {
  constructor(socket) {
    this.socket = socket;
    this.id = 0;
    this.pending = new Map();
    this.listeners = new Map();
    socket.addEventListener("message", ({ data }) => {
      const message = JSON.parse(String(data));
      if (message.id) {
        const pending = this.pending.get(message.id);
        if (!pending) return;
        clearTimeout(pending.timer);
        this.pending.delete(message.id);
        if (message.error) pending.reject(fixedFailure()); else pending.resolve(message.result ?? {});
      } else {
        const key = `${message.sessionId ?? ""}:${message.method}`;
        for (const fn of this.listeners.get(key) ?? []) fn(message.params ?? {});
      }
    });
    socket.addEventListener("close", () => {
      for (const pending of this.pending.values()) { clearTimeout(pending.timer); pending.reject(fixedFailure()); }
      this.pending.clear();
    });
  }
  on(session, method, fn) {
    const key = `${session ?? ""}:${method}`;
    const values = this.listeners.get(key) ?? new Set();
    values.add(fn); this.listeners.set(key, values);
    return () => values.delete(fn);
  }
  send(session, method, params = {}) {
    const id = ++this.id;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => { this.pending.delete(id); reject(fixedFailure()); }, 15000);
      this.pending.set(id, { resolve, reject, timer });
      this.socket.send(JSON.stringify({ id, method, params, ...(session ? { sessionId: session } : {}) }));
    });
  }
  async evaluate(session, expression) {
    const value = await this.send(session, "Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
    if (value.exceptionDetails) throw fixedFailure();
    return value.result?.value;
  }
}

async function listen(server) {
  await new Promise((resolve, reject) => { server.once("error", reject); server.listen(0, "127.0.0.1", resolve); });
  return server.address().port;
}
async function close(server) { if (server?.listening) await new Promise((resolve) => server.close(resolve)); }

async function executable() {
  for (const candidate of ["C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe", "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe", "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe", "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe"]) {
    try { await access(candidate); return candidate; } catch { /* fixed installed candidates only */ }
  }
  throw fixedFailure();
}

async function browserGate(setup, input, core, attacker, counters, profile) {
  const preview = `http://v-${setup.artifact_version_id}.aria-preview.test:${input.preview_port}`;
  const prefix = `${preview}/p/${input.token}/`;
  const reservation = tcpServer();
  const debug = await listen(reservation); await close(reservation);
  const handle = spawn(await executable(), ["--headless=new", `--remote-debugging-port=${debug}`, `--user-data-dir=${profile}`, `--host-resolver-rules=MAP ${CORE} 127.0.0.1,MAP ${ATTACKER} 127.0.0.1,MAP v-${setup.artifact_version_id}.aria-preview.test 127.0.0.1`, "--disable-background-networking", "--disable-component-update", "--disable-domain-reliability", "--disable-extensions", "--disable-features=MediaRouter,OptimizationHints,Translate", "--disable-sync", "--metrics-recording-only", "--no-default-browser-check", "--no-first-run", "--no-proxy-server", "about:blank"], { stdio: "ignore", windowsHide: true });
  let protocol;
  let stage = "startup";
  let unexpected = 0;
  const unexpectedClasses = { synthetic_data_probe: 0, external_network: 0, other: 0 };
  let localProbeArmed = false;
  let localProbeRequests = 0;
  let cspBlockedDocuments = 0;
  let securityEntries = 0;
  let downloads = 0;
  let responseHeadersSafe = true;
  let fontRequests = 0;
  const attached = new Map();
  try {
    let metadata;
    for (let index = 0; index < 120; index++) {
      if (handle.exitCode !== null) throw fixedFailure();
      try { metadata = await fetch(`http://127.0.0.1:${debug}/json/version`).then((r) => r.json()); if (metadata.webSocketDebuggerUrl) break; } catch { /* bounded startup only */ }
      await delay(100);
    }
    if (!metadata?.webSocketDebuggerUrl) throw fixedFailure();
    const socket = new WebSocket(metadata.webSocketDebuggerUrl);
    await new Promise((resolve, reject) => { socket.addEventListener("open", resolve, { once: true }); socket.addEventListener("error", reject, { once: true }); });
    protocol = new Protocol(socket);
    protocol.on(null, "Browser.downloadWillBegin", () => { downloads++; });
    await protocol.send(null,"Browser.setDownloadBehavior",{behavior:"allow",downloadPath:path.join(profile,"downloads"),eventsEnabled:true});
    const allowedOrigins = new Set([core, attacker, preview]);
    async function enable(id) {
      protocol.on(id, "Target.attachedToTarget", attach);
      protocol.on(id, "Fetch.requestPaused", (event) => {
        const kind = classifyControlledRequest(event.request.url, allowedOrigins, localProbeArmed);
        const allowed = kind !== "unexpected";
        if (kind === "local_probe") localProbeRequests++;
        if (!allowed) {
          unexpected++;
          if (event.request.url === "data:text/plain,synthetic") unexpectedClasses.synthetic_data_probe++;
          else if (/^https?:/.test(event.request.url)) unexpectedClasses.external_network++;
          else unexpectedClasses.other++;
        }
        void protocol.send(id, allowed ? "Fetch.continueRequest" : "Fetch.failRequest", { requestId: event.requestId, ...(!allowed ? { errorReason: "BlockedByClient" } : {}) }).catch(() => {});
      });
      protocol.on(id, "Network.requestWillBeSent", (event) => { if (event.type === "Font") fontRequests++; });
      protocol.on(id, "Network.loadingFailed", (event) => { if (event.type === "Document" && event.blockedReason === "csp") cspBlockedDocuments++; });
      protocol.on(id, "Log.entryAdded", ({ entry }) => { if (entry.source === "security") securityEntries++; });
      protocol.on(id, "Network.responseReceived", ({ response }) => {
        if (response.url.startsWith(preview + "/")) {
          const headers = Object.fromEntries(Object.entries(response.headers).map(([k,v]) => [k.toLowerCase(),v]));
          responseHeadersSafe &&= headers["cache-control"] === "no-store" && headers["referrer-policy"] === "no-referrer" && !("access-control-allow-origin" in headers);
        }
      });
      await Promise.all([protocol.send(id, "Page.enable"), protocol.send(id, "Runtime.enable"), protocol.send(id, "Network.enable"), protocol.send(id, "Log.enable"), protocol.send(id, "Fetch.enable", { patterns: [{ urlPattern: "*" }] }), protocol.send(id, "Target.setAutoAttach", { autoAttach: true, waitForDebuggerOnStart: true, flatten: true })]);
    }
    // Auto-attach before navigation so OOPIF requests are observed before execution.
    function attach({ sessionId, targetInfo }) {
      const ready = enable(sessionId).then(() => protocol.send(sessionId, "Runtime.runIfWaitingForDebugger"));
      attached.set(targetInfo.targetId, { sessionId, ready });
      void ready.catch(() => {});
    }
    protocol.on(null, "Target.attachedToTarget", attach);
    await protocol.send(null, "Target.setAutoAttach", { autoAttach: true, waitForDebuggerOnStart: true, flatten: true });
    const { targetId } = await protocol.send(null, "Target.createTarget", { url: "about:blank" });
    for (let i = 0; i < 120 && !attached.has(targetId); i++) await delay(100);
    const main = attached.get(targetId); if (!main) throw fixedFailure(); await main.ready;
    async function child() {
      for (let i = 0; i < 120; i++) {
        const targets = await protocol.send(null, "Target.getTargets");
        const iframe = targets.targetInfos.find((t) => t.type === "iframe" && t.url.startsWith(prefix));
        if (iframe && attached.has(iframe.targetId)) { const entry = attached.get(iframe.targetId); await entry.ready; return entry.sessionId; }
        await delay(100);
      }
      throw fixedFailure();
    }
    stage = "pages";
    await protocol.send(main.sessionId, "Page.navigate", { url: core + "/" });
    stage = "iframe_attach";
    let childId = await child();
    const pageResults = [];
    const pageFailures = new Set();
    let formSeen = false;
    for (const file of setup.pages) {
      await protocol.evaluate(main.sessionId, `document.querySelector('iframe').src=${JSON.stringify(prefix + file)}; true`);
      stage = "page_ready";
      for (let i = 0; i < 120; i++) {
        childId = await child();
        const ready = await protocol.evaluate(childId, `document.readyState==='complete' && location.href===${JSON.stringify(prefix + file)}`).catch(() => false);
        if (ready) break;
        await delay(100);
      }
      stage = "page_resources";
      // Native lazy/async images are not complete merely because DOM readyState is complete.
      // Exercise normal scrolling and decoding; do not rewrite loading attributes or source.
      await protocol.evaluate(childId, `(async()=>{
        for(const image of document.images){
          image.scrollIntoView({block:'center'});
          await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
          await image.decode().catch(()=>false);
        }
        return true;
      })()`);
      const result = await protocol.evaluate(childId, `(() => {
        const main=document.querySelector('main'); const style=main&&getComputedStyle(main);
        const roots=[...document.querySelectorAll('a[href],img[src],link[rel=stylesheet][href]')];
        // Sandbox security origin is opaque; URL authority is the configured Preview origin,
        // not the document's origin string. Both the namespace and exact declared files matter.
        const references=roots.every(e=>{const u=new URL(e.getAttribute(e.tagName==='IMG'?'src':'href'),location.href);return u.origin===${JSON.stringify(preview)}&&u.href.startsWith(${JSON.stringify(prefix)})&&${JSON.stringify(setup.pages.concat(["assets/styles.css", "generation-fixtures/media.svg"]))}.includes(u.href.slice(${prefix.length}));});
        const inputs=[...document.querySelectorAll('input,textarea,select')]; const required=inputs.find(e=>e.required);
        const emptyInvalid=required?!required.checkValidity():true;
        if(required){required.value=required.type==='email'?'synthetic@example.test':'synthetic';required.focus();}
        const form=required?(emptyInvalid&&required.checkValidity()&&document.forms.length===0):null;
        for(const b of document.querySelectorAll('button')){if(b.type==='button')b.click();}
        return {loaded:location.href===${JSON.stringify(prefix + file)}, one_main:!!main&&document.querySelectorAll('main').length===1, one_h1:document.querySelectorAll('h1').length===1, rtl:document.documentElement.dir==='rtl'&&style.direction==='rtl', css:document.styleSheets.length>0&&style.fontFamily.includes('system-ui'), images:[...document.images].every(e=>e.complete&&e.naturalWidth>0), references, script_free:document.scripts.length===0, form};
      })()`);
      if (result.form !== null) { formSeen = true; if (!result.form) throw fixedFailure(); }
      if (result.form !== null) {
        await protocol.send(childId,"Input.dispatchKeyEvent",{type:"keyDown",key:"Enter",code:"Enter",windowsVirtualKeyCode:13});
        await protocol.send(childId,"Input.dispatchKeyEvent",{type:"keyUp",key:"Enter",code:"Enter",windowsVirtualKeyCode:13});
      }
      pageResults.push(Object.entries(result).filter(([k]) => k !== "form").every(([,v]) => v === true));
      for (const [key,value] of Object.entries(result)) if(key !== "form" && value !== true) pageFailures.add(key);
    }
    stage = "navigation";
    await protocol.evaluate(main.sessionId, `document.querySelector('iframe').src=${JSON.stringify(prefix + "index.html")}; true`);
    await delay(500); childId = await child();
    const link = await protocol.evaluate(childId, `(() => {const a=[...document.querySelectorAll('a[href]')].find(e=>e.href!==location.href);if(!a)return null;const expected=a.href;a.click();return expected;})()`);
    let navigation = true;
    if (link) { await delay(500); childId = await child(); navigation = await protocol.evaluate(childId, `location.href===${JSON.stringify(link)}`); }
    stage = "isolation";
    localProbeArmed = true;
    const isolation = await protocol.evaluate(childId, `(async()=>{
      const denied=f=>{try{f();return false;}catch{return true;}};
      const checks={opaque:self.origin==='null',parent_dom:denied(()=>parent.document.body),parent_cookie:denied(()=>parent.document.cookie),parent_storage:denied(()=>parent.localStorage.length),own_storage:denied(()=>localStorage.length),core_api:await fetch(${JSON.stringify(core + "/api/sentinel")}).then(()=>false,()=>true),popup:window.open(${JSON.stringify(core + "/popup")})===null};
      const script=document.createElement('script');script.textContent='globalThis.syntheticForbiddenInline=true';document.head.append(script);checks.inline=globalThis.syntheticForbiddenInline!==true;
      const form=document.createElement('form');form.method='POST';form.action=${JSON.stringify(core + "/api/form")};document.body.append(form);form.submit();
      const top=document.createElement('a');top.href=${JSON.stringify(core + "/escaped")};top.target='_top';document.body.append(top);top.click();
      const download=document.createElement('a');download.href='data:text/plain,synthetic';download.download='synthetic.txt';document.body.append(download);download.click();
      return Object.values(checks).every(Boolean);
    })()`);
    await delay(300);
    const parentStayed = await protocol.evaluate(main.sessionId, `location.href===${JSON.stringify(core + "/")}`);
    const sandbox = await protocol.evaluate(main.sessionId, `document.querySelector('iframe').getAttribute('sandbox')==='allow-scripts'&&document.querySelector('iframe').referrerPolicy==='no-referrer'`);
    stage = "unauthorized_embed";
    const before = cspBlockedDocuments;
    const securityBefore = securityEntries;
    await protocol.send(main.sessionId, "Page.navigate", { url: attacker + "/" });
    await delay(2000);
    const candidates = (await protocol.send(null,"Target.getTargets")).targetInfos.filter(t=>t.type==='iframe'&&t.url.startsWith(prefix));
    let readable = false;
    for (const candidate of candidates) {
      const entry = attached.get(candidate.targetId);
      if(entry) { await entry.ready; readable ||= await protocol.evaluate(entry.sessionId,"!!document.querySelector('main')").catch(()=>false); }
    }
    const unauthorized = !readable && (cspBlockedDocuments > before || securityEntries > securityBefore);
    const checks = { pages_pass: pageResults.every(Boolean), navigation, isolation, sandbox, parent_stayed: parentStayed, unauthorized_embed: unauthorized, headers: responseHeadersSafe, zero_fonts: fontRequests === 0, zero_unexpected_network: unexpected === 0, zero_core_effects: counters.effects === 0, zero_downloads: downloads === 0 };
    return { status: Object.values(checks).every(Boolean) ? "PASS" : "FAIL", browser: (await protocol.send(null, "Browser.getVersion")).product, pages: pageResults.length, form_seen: formSeen, page_failures:[...pageFailures].sort(), unexpected_classes: unexpectedClasses, local_probe_requests: localProbeRequests, ...checks };
  } catch { return { status: "FAIL", error_code: "BROWSER_GATE_FAILED", stage }; }
  finally {
    if (protocol) { try { await protocol.send(null, "Browser.close"); } catch { /* bounded */ } protocol.socket.close(); }
    if (handle.exitCode === null) handle.kill();
    if (handle.exitCode === null) await Promise.race([new Promise((r)=>handle.once("exit",r)),delay(3000)]);
  }
}

async function run() {
  const lines = createInterface({ input: process.stdin });
  const iterator = lines[Symbol.asyncIterator]();
  const setup = validateSetup(JSON.parse((await iterator.next()).value));
  const profile = path.join(setup.profile_parent, "browser-profile-" + randomUUID());
  let state;
  let coreOrigin, attackerOrigin;
  const counters = { effects: 0 };
  const handler = (attacker) => (request, response) => {
    const expectedHost = new URL(attacker ? attackerOrigin : coreOrigin).host;
    if (request.headers.host !== expectedHost || request.url !== "/" || !state) { if (["/api/sentinel","/api/form","/popup","/escaped","/download-sentinel"].includes(request.url)) counters.effects++; response.writeHead(404,{"Cache-Control":"no-store","Referrer-Policy":"no-referrer"}).end(); return; }
    const src = `http://v-${setup.artifact_version_id}.aria-preview.test:${state.preview_port}/p/${state.token}/index.html`;
    // Only the volatile test wrapper includes a token; derivative/source bytes are untouched.
    response.writeHead(200,{"Content-Type":"text/html; charset=utf-8","Cache-Control":"no-store","Referrer-Policy":"no-referrer"}).end(`<!doctype html><html><head><meta charset="utf-8"></head><body><iframe title="Synthetic Preview" sandbox="allow-scripts" referrerpolicy="no-referrer" src="${src}"></iframe></body></html>`);
  };
  const core = createServer(handler(false)); const attacker = createServer(handler(true));
  let result;
  try {
    coreOrigin = `http://${CORE}:${await listen(core)}`; attackerOrigin = `http://${ATTACKER}:${await listen(attacker)}`;
    process.stdout.write(JSON.stringify({ core_port:new URL(coreOrigin).port })+"\n");
    state = JSON.parse((await iterator.next()).value);
    if (Object.keys(state).sort().join(",") !== "preview_port,token" || !Number.isInteger(state.preview_port) || state.preview_port<1 || state.preview_port>65535 || !/^[A-Za-z0-9_-]{43}$/.test(state.token)) throw fixedFailure();
    await mkdir(profile);
    result = await browserGate(setup,state,coreOrigin,attackerOrigin,counters,profile);
  } finally {
    lines.close(); await close(core); await close(attacker);
    await rm(profile,{recursive:true,force:true});
  }
  process.stdout.write(JSON.stringify(result)+"\n");
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  run().catch(()=>{process.stdout.write(JSON.stringify({status:"FAIL",error_code:"BROWSER_GATE_FAILED",stage:"setup_or_cleanup"})+"\n");process.exitCode=1;});
}
