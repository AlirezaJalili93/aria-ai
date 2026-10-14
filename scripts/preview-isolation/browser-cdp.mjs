import { spawn } from "node:child_process";
import { access } from "node:fs/promises";
import { createServer } from "node:net";

const CANDIDATES = process.platform === "win32"
  ? [
      "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
      "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
      "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
      "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe"
    ]
  : ["google-chrome", "chromium", "chromium-browser"];

async function browserPath() {
  if (process.env.ARIA_0101_BROWSER_PATH) return process.env.ARIA_0101_BROWSER_PATH;
  for (const candidate of CANDIDATES) {
    try {
      if (process.platform !== "win32") return candidate;
      await access(candidate);
      return candidate;
    } catch {
      // Continue to the next fixed candidate.
    }
  }
  throw new Error("0101_CHROMIUM_BROWSER_REQUIRED");
}

async function reservePort() {
  const server = createServer();
  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolve);
  });
  const address = server.address();
  if (!address || typeof address === "string") throw new Error("0101_BROWSER_PORT_FAILED");
  await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
  return address.port;
}

class Session {
  constructor(socket) {
    this.socket = socket;
    this.nextId = 1;
    this.pending = new Map();
    this.targetPending = new Map();
    this.targetListeners = new Map();
    this.attachedTargets = new Map();
    this.listeners = new Map();
    socket.addEventListener("message", (event) => this.receive(event));
  }
  receive(event) {
    const message = JSON.parse(String(event.data));
    if (message.sessionId && message.method && message.method !== "Target.receivedMessageFromTarget") {
      for (const listener of this.targetListeners.get(message.sessionId)?.get(message.method) ?? []) listener(message.params ?? {});
      return;
    }
    if (message.sessionId && message.id && this.targetPending.has(`${message.sessionId}:${message.id}`)) {
      const pending = this.targetPending.get(`${message.sessionId}:${message.id}`);
      this.targetPending.delete(`${message.sessionId}:${message.id}`);
      if (message.error) pending.reject(new Error(`0101_CDP_TARGET_ERROR:${message.error.message}`));
      else pending.resolve(message.result ?? {});
      return;
    }
    if (message.method === "Target.receivedMessageFromTarget") {
      const targetMessage = JSON.parse(message.params.message);
      if (targetMessage.id && this.targetPending.has(`${message.params.sessionId}:${targetMessage.id}`)) {
        const pending = this.targetPending.get(`${message.params.sessionId}:${targetMessage.id}`);
        this.targetPending.delete(`${message.params.sessionId}:${targetMessage.id}`);
        if (targetMessage.error) pending.reject(new Error(`0101_CDP_TARGET_ERROR:${targetMessage.error.message}`));
        else pending.resolve(targetMessage.result ?? {});
      } else {
        for (const listener of this.targetListeners.get(message.params.sessionId)?.get(targetMessage.method) ?? []) listener(targetMessage.params ?? {});
      }
      return;
    }
    if (message.method === "Target.attachedToTarget") {
      this.attachedTargets.set(message.params.targetInfo.targetId, message.params.sessionId);
    }
    if (message.id) {
      const pending = this.pending.get(message.id);
      if (!pending) return;
      this.pending.delete(message.id);
      if (message.error) pending.reject(new Error(`0101_CDP_ERROR:${message.error.message}`));
      else pending.resolve(message.result ?? {});
      return;
    }
    for (const listener of this.listeners.get(message.method) ?? []) listener(message.params ?? {});
  }
  on(method, listener) {
    const set = this.listeners.get(method) ?? new Set();
    set.add(listener);
    this.listeners.set(method, set);
    return () => set.delete(listener);
  }
  send(method, params = {}) {
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.socket.send(JSON.stringify({ id, method, params }));
    });
  }
  sendToTarget(sessionId, method, params = {}) {
    const id = this.nextId++;
    const key = `${sessionId}:${id}`;
    const result = new Promise((resolve, reject) => this.targetPending.set(key, { resolve, reject }));
    this.socket.send(JSON.stringify({ id, sessionId, method, params }));
    return result;
  }
  onTarget(sessionId, method, listener) {
    const methods = this.targetListeners.get(sessionId) ?? new Map();
    const listeners = methods.get(method) ?? new Set();
    listeners.add(listener);
    methods.set(method, listeners);
    this.targetListeners.set(sessionId, methods);
    return () => listeners.delete(listener);
  }
  waitFor(method, timeoutMs = 15000) {
    return new Promise((resolve, reject) => {
      const remove = this.on(method, (params) => {
        clearTimeout(timer);
        remove();
        resolve(params);
      });
      const timer = setTimeout(() => {
        remove();
        reject(new Error(`0101_CDP_TIMEOUT:${method}`));
      }, timeoutMs);
    });
  }
}

class TargetSession {
  constructor(root, sessionId) { this.root = root; this.sessionId = sessionId; }
  send(method, params = {}) { return this.root.sendToTarget(this.sessionId, method, params); }
  on(method, listener) { return this.root.onTarget(this.sessionId, method, listener); }
  waitFor(method, timeoutMs = 15000) {
    return new Promise((resolve, reject) => {
      const remove = this.on(method, (params) => {
        clearTimeout(timer);
        remove();
        resolve(params);
      });
      const timer = setTimeout(() => {
        remove();
        reject(new Error(`0101_CDP_TIMEOUT:${method}`));
      }, timeoutMs);
    });
  }
}

async function connect(url) {
  const socket = new WebSocket(url);
  await new Promise((resolve, reject) => {
    socket.addEventListener("open", resolve, { once: true });
    socket.addEventListener("error", reject, { once: true });
  });
  return new Session(socket);
}

async function devTools(port, processHandle) {
  for (let index = 0; index < 120; index += 1) {
    if (processHandle.exitCode !== null) throw new Error("0101_BROWSER_EXITED_EARLY");
    try {
      const [version, list] = await Promise.all([
        fetch(`http://127.0.0.1:${port}/json/version`).then((response) => response.json()),
        fetch(`http://127.0.0.1:${port}/json/list`).then((response) => response.json())
      ]);
      const page = list.find((item) => item.type === "page" && item.id);
      if (version.webSocketDebuggerUrl && page) {
        return { browserWebSocketUrl: version.webSocketDebuggerUrl, pageTargetId: page.id };
      }
    } catch {
      // Bounded startup polling.
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error("0101_BROWSER_DEVTOOLS_TIMEOUT");
}

function evaluate(session, expression, contextId) {
  return session.send("Runtime.evaluate", {
    expression,
    contextId,
    awaitPromise: true,
    returnByValue: true
  }).then((result) => {
    if (result.exceptionDetails) throw new Error("0101_BROWSER_EVALUATION_FAILED");
    return result.result?.value;
  });
}

async function navigate(session, url) {
  const loaded = session.waitFor("Page.loadEventFired");
  const result = await session.send("Page.navigate", { url });
  if (result.errorText) throw new Error(`0101_NAVIGATION_FAILED:${result.errorText}`);
  await loaded;
  await new Promise((resolve) => setTimeout(resolve, 2000));
}

async function attachOutOfProcessIframe(session, expectedOrigin) {
  let lastTargets = [];
  for (let attempt = 0; attempt < 20; attempt += 1) {
    const targets = await session.send("Target.getTargets");
    lastTargets = targets.targetInfos ?? [];
    const target = (targets.targetInfos ?? []).find((item) => item.type === "iframe" && item.url.startsWith(expectedOrigin));
    if (target) {
      await new Promise((resolve) => setTimeout(resolve, 500));
      let sessionId = session.attachedTargets.get(target.targetId);
      if (!sessionId) ({ sessionId } = await session.send("Target.attachToTarget", { targetId: target.targetId, flatten: true }));
      const child = new TargetSession(session, sessionId);
      await child.send("Runtime.enable");
      await child.send("Page.enable");
      return child;
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  const summary = lastTargets.map((item) => `${item.type}:${item.url}`).join(",");
  throw new Error(`0101_OOPIF_TARGET_NOT_FOUND:${summary}`);
}

function frameIds(tree) {
  const values = [tree.frame.id];
  for (const child of tree.childFrames ?? []) values.push(...frameIds(child));
  return values;
}

export async function runPreviewIsolationBrowserGate({
  coreOrigin,
  previewOrigin,
  attackerOrigin,
  profileRoot,
  serverCounters
}) {
  const executable = await browserPath();
  const debuggingPort = await reservePort();
  const hosts = [new URL(coreOrigin).hostname, new URL(previewOrigin).hostname, new URL(attackerOrigin).hostname];
  const browser = spawn(executable, [
    "--headless=new",
    `--remote-debugging-port=${debuggingPort}`,
    `--user-data-dir=${profileRoot}`,
    `--host-resolver-rules=${hosts.map((host) => `MAP ${host} 127.0.0.1`).join(",")}`,
    "--disable-background-networking",
    "--disable-component-update",
    "--disable-domain-reliability",
    "--disable-extensions",
    "--disable-features=MediaRouter,OptimizationHints,Translate",
    "--disable-sync",
    "--metrics-recording-only",
    "--no-default-browser-check",
    "--no-first-run",
    "--no-proxy-server",
    "about:blank"
  ], { stdio: "ignore", windowsHide: true });
  let rootSession;
  let stage = "browser_startup";
  try {
    stage = "devtools_discovery";
    const endpoint = await devTools(debuggingPort, browser);
    rootSession = await connect(endpoint.browserWebSocketUrl);
    stage = "page_attach";
    const { sessionId } = await rootSession.send("Target.attachToTarget", {
      targetId: endpoint.pageTargetId,
      flatten: true
    });
    const session = new TargetSession(rootSession, sessionId);
    const failures = [];
    const cspMessages = [];
    session.on("Network.loadingFailed", (event) => failures.push({ type: event.type, blockedReason: event.blockedReason, errorText: event.errorText }));
    session.on("Log.entryAdded", ({ entry }) => {
      if (/content security policy|refused to/i.test(entry.text ?? "")) cspMessages.push(entry.text);
    });
    await Promise.all([
      session.send("Page.enable"),
      session.send("Runtime.enable"),
      session.send("Network.enable"),
      session.send("Log.enable"),
      rootSession.send("Target.setDiscoverTargets", { discover: true })
    ]);
    await session.send("Network.clearBrowserCache");
    await session.send("Network.clearBrowserCookies");
    stage = "core_navigation";
    await navigate(session, `${coreOrigin}/`);
    stage = "core_state_setup";
    await evaluate(session, `document.cookie="aria_core_secret=synthetic-sentinel; SameSite=Lax"; localStorage.setItem("aria_core_secret", "synthetic-sentinel"); true`);
    stage = "preview_attach";
    const child = await attachOutOfProcessIframe(rootSession, previewOrigin);
    child.on("Network.loadingFailed", (event) => failures.push({ type: event.type, blockedReason: event.blockedReason, errorText: event.errorText }));
    child.on("Log.entryAdded", ({ entry }) => {
      if (/content security policy|refused to/i.test(entry.text ?? "")) cspMessages.push(entry.text);
    });
    stage = "preview_resource_check";
    const resource = await evaluate(child, `(async () => {
      const fontFamily = getComputedStyle(document.querySelector('.aria-gen-page')).fontFamily;
      return {
        image_loaded: [...document.images].length > 0 && [...document.images].every((image) => image.complete && image.naturalWidth > 0),
        system_font_rendered: fontFamily.includes('system-ui'),
        font_network_requests_zero: ${JSON.stringify(serverCounters.font_requests === 0)},
        style_loaded: getComputedStyle(document.querySelector('.aria-gen-page')).direction === 'rtl',
        script_loaded: globalThis.__ARIA_0101_RUNTIME__ === true,
        inline_hash_script_loaded: document.documentElement.dataset.inlineHash === 'verified',
        inline_script_count: document.querySelectorAll('script:not([src])').length
      };
    })()`);

    stage = "preview_isolation_check";
    const isolation = await evaluate(child, `(async () => {
      const denied = (operation) => { try { operation(); return false; } catch { return true; } };
      const parent_dom_denied = denied(() => parent.document.body.textContent);
      const parent_cookie_denied = denied(() => parent.document.cookie);
      const parent_storage_denied = denied(() => parent.localStorage.length);
      const own_storage_denied = denied(() => localStorage.length);
      const core_api_denied = await fetch(${JSON.stringify(`${coreOrigin}/api/sentinel`)}).then(() => false, () => true);
      const inline = document.createElement('script');
      inline.textContent = 'globalThis.__ARIA_0101_INLINE__ = true';
      document.head.append(inline);
      await new Promise((resolve) => setTimeout(resolve, 50));
      const inline_script_denied = globalThis.__ARIA_0101_INLINE__ !== true;
      const popup_denied = window.open(${JSON.stringify(`${coreOrigin}/popup`)}) === null;
      return { parent_dom_denied, parent_cookie_denied, parent_storage_denied, own_storage_denied, core_api_denied, inline_script_denied, popup_denied };
    })()`);
    stage = "preview_forbidden_actions";
    await evaluate(child, `(() => {
      const form = document.createElement('form');
      form.method = 'POST'; form.action = ${JSON.stringify(`${coreOrigin}/api/form`)};
      document.body.append(form); form.submit();
      const download = document.createElement('a');
      download.href = ${JSON.stringify(`${coreOrigin}/download-sentinel`)}; download.download = 'sentinel.txt';
      document.body.append(download); download.click();
      const topLink = document.createElement('a');
      topLink.href = ${JSON.stringify(`${coreOrigin}/escaped`)}; topLink.target = '_top';
      document.body.append(topLink); topLink.click();
      return true;
    })()`).catch(() => false);
    await new Promise((resolve) => setTimeout(resolve, 300));
    const parentHref = await evaluate(session, "location.href");
    const networkDenied = {
      form_submission_denied: serverCounters.form === 0,
      download_denied: serverCounters.download === 0,
      top_navigation_denied: parentHref === `${coreOrigin}/`
    };

    stage = "contact_navigation";
    await navigate(session, `${coreOrigin}/contact-proof`);
    stage = "contact_preview_attach";
    const contactChild = await attachOutOfProcessIframe(rootSession, previewOrigin);
    stage = "contact_form_check";
    const simpleForm = await evaluate(contactChild, `(() => {
      const input = document.querySelector('input[required]');
      if (!input) return false;
      const emptyInvalid = !input.checkValidity();
      input.value = 'synthetic';
      return emptyInvalid && input.checkValidity() && document.forms.length === 0;
    })()`);

    const failureCountBefore = failures.length;
    const cspCountBefore = cspMessages.length;
    const previewRequestsBefore = serverCounters.preview_requests;
    stage = "attacker_navigation";
    await navigate(session, `${attackerOrigin}/`);
    await new Promise((resolve) => setTimeout(resolve, 500));
    const targets = await rootSession.send("Target.getTargets");
    const attackerHasPreviewTarget = (targets.targetInfos ?? []).some((item) => item.type === "iframe" && item.url.startsWith(previewOrigin));
    const unauthorized_embed_denied = cspMessages.length > cspCountBefore
      || failures.slice(failureCountBefore).some((item) => item.type === "Document" && item.blockedReason)
      || (!attackerHasPreviewTarget && serverCounters.preview_requests === previewRequestsBefore);

    stage = "complete";
    return {
      browser: executable.endsWith("msedge.exe") ? "Microsoft Edge" : "Google Chrome",
      resources: resource,
      isolation: { ...isolation, ...networkDenied, simple_form_local_validation: simpleForm, unauthorized_embed_denied },
      failed_requests: failures,
      csp_violation_count: cspMessages.length,
      oopif: true
    };
  } catch (error) {
    const code = error instanceof Error ? error.message : "0101_BROWSER_GATE_FAILED";
    throw new Error(`${stage}:${code}`);
  } finally {
    if (rootSession) {
      try { await rootSession.send("Browser.close"); } catch { /* Transport closes first. */ }
      rootSession.socket.close();
    }
    if (browser.exitCode === null) browser.kill();
    await Promise.race([
      new Promise((resolve) => browser.once("exit", resolve)),
      new Promise((resolve) => setTimeout(resolve, 3000))
    ]);
  }
}
