import { spawn } from "node:child_process";
import { createServer } from "node:net";

const CHROME_CANDIDATES = process.platform === "win32"
  ? [
      "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
      "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
      "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
      "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe"
    ]
  : ["google-chrome", "chromium", "chromium-browser"];

async function pathExists(filePath) {
  if (process.platform !== "win32") return true;
  const { access } = await import("node:fs/promises");
  try {
    await access(filePath);
    return true;
  } catch {
    return false;
  }
}

async function findBrowser() {
  if (process.env.ARIA_0098_BROWSER_PATH) return process.env.ARIA_0098_BROWSER_PATH;
  for (const candidate of CHROME_CANDIDATES) {
    if (await pathExists(candidate)) return candidate;
  }
  throw new Error("0098_CHROMIUM_BROWSER_REQUIRED");
}

async function reservePort() {
  const server = createServer();
  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolve);
  });
  const address = server.address();
  if (!address || typeof address === "string") throw new Error("0098_BROWSER_PORT_FAILED");
  await new Promise((resolve, reject) => server.close((error) => (error ? reject(error) : resolve())));
  return address.port;
}

async function waitForDevTools(port, browserProcess) {
  const endpoint = `http://127.0.0.1:${port}`;
  for (let attempt = 0; attempt < 100; attempt += 1) {
    if (browserProcess.exitCode !== null) throw new Error("0098_BROWSER_EXITED_EARLY");
    try {
      const targets = await fetch(`${endpoint}/json/list`).then((response) => response.json());
      const page = targets.find((target) => target.type === "page" && target.webSocketDebuggerUrl);
      if (page) return { endpoint, page };
    } catch {
      // Browser startup is bounded by the loop below.
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error("0098_BROWSER_DEVTOOLS_TIMEOUT");
}

class CdpSession {
  constructor(socket) {
    this.socket = socket;
    this.nextId = 1;
    this.pending = new Map();
    this.listeners = new Map();
    socket.addEventListener("message", (event) => this.#receive(event));
    socket.addEventListener("close", () => {
      for (const { reject } of this.pending.values()) reject(new Error("0098_CDP_CLOSED"));
      this.pending.clear();
    });
  }

  #receive(event) {
    const message = JSON.parse(String(event.data));
    if (message.id) {
      const pending = this.pending.get(message.id);
      if (!pending) return;
      this.pending.delete(message.id);
      if (message.error) pending.reject(new Error(`0098_CDP_ERROR: ${message.error.message}`));
      else pending.resolve(message.result ?? {});
      return;
    }
    for (const listener of this.listeners.get(message.method) ?? []) listener(message.params ?? {});
  }

  on(method, listener) {
    const listeners = this.listeners.get(method) ?? new Set();
    listeners.add(listener);
    this.listeners.set(method, listeners);
    return () => listeners.delete(listener);
  }

  waitFor(method, timeoutMs = 15000) {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        remove();
        reject(new Error(`0098_CDP_EVENT_TIMEOUT: ${method}`));
      }, timeoutMs);
      const remove = this.on(method, (params) => {
        clearTimeout(timer);
        remove();
        resolve(params);
      });
    });
  }

  send(method, params = {}) {
    const id = this.nextId;
    this.nextId += 1;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.socket.send(JSON.stringify({ id, method, params }));
    });
  }

  close() {
    this.socket.close();
  }
}

async function connect(webSocketDebuggerUrl) {
  const socket = new WebSocket(webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    socket.addEventListener("open", resolve, { once: true });
    socket.addEventListener("error", () => reject(new Error("0098_CDP_CONNECT_FAILED")), { once: true });
  });
  return new CdpSession(socket);
}

function normalizePagePath(value) {
  const url = new URL(value, "http://aria.invalid");
  const path = url.pathname.length > 1 && url.pathname.endsWith("/") ? url.pathname.slice(0, -1) : url.pathname;
  return path || "/";
}

function evaluate(session, expression) {
  return session.send("Runtime.evaluate", {
    expression,
    awaitPromise: true,
    returnByValue: true
  }).then((result) => {
    if (result.exceptionDetails) throw new Error("0098_BROWSER_EVALUATION_FAILED");
    return result.result?.value;
  });
}

async function navigate(session, url) {
  const loaded = session.waitFor("Page.loadEventFired");
  const result = await session.send("Page.navigate", { url });
  if (result.errorText) throw new Error(`0098_BROWSER_NAVIGATION_FAILED: ${result.errorText}`);
  await loaded;
  await new Promise((resolve) => setTimeout(resolve, 100));
}

export async function runBrowserSecurityGate({ origin, pagePaths, profileRoot }) {
  const executable = await findBrowser();
  const port = await reservePort();
  const browserProcess = spawn(
    executable,
    [
      "--headless=new",
      `--remote-debugging-port=${port}`,
      `--user-data-dir=${profileRoot}`,
      "--disable-background-networking",
      "--disable-component-update",
      "--disable-default-apps",
      "--disable-domain-reliability",
      "--disable-extensions",
      "--disable-features=MediaRouter,OptimizationHints,Translate",
      "--disable-sync",
      "--metrics-recording-only",
      "--no-default-browser-check",
      "--no-first-run",
      "--no-proxy-server",
      "--safebrowsing-disable-auto-update",
      "about:blank"
    ],
    { stdio: "ignore", windowsHide: true }
  );
  let session;
  const allowedPaths = new Set(pagePaths.map(normalizePagePath));
  const observed = [];
  const blocked = [];
  const websocketAttempts = [];
  const runtimeExceptions = [];
  let phase = "control";
  try {
    const { page } = await waitForDevTools(port, browserProcess);
    session = await connect(page.webSocketDebuggerUrl);
    session.on("Runtime.exceptionThrown", () => runtimeExceptions.push(phase));
    session.on("Network.webSocketCreated", ({ url }) => {
      websocketAttempts.push({ phase, external: !String(url).startsWith(origin) });
    });
    session.on("Fetch.requestPaused", (params) => {
      const requestUrl = new URL(params.request.url);
      const sameOrigin = requestUrl.origin === origin;
      const pagePath = normalizePagePath(requestUrl.pathname);
      const methodAllowed = params.request.method === "GET" || params.request.method === "HEAD";
      const navigationAllowed = params.resourceType !== "Document" || allowedPaths.has(pagePath);
      const apiDenied = pagePath === "/api" || pagePath.startsWith("/api/");
      const imageAllowed = params.resourceType !== "Image" || pagePath.startsWith("/generation-fixtures/");
      const credentialsAbsent = !Object.keys(params.request.headers ?? {}).some((name) =>
        ["authorization", "cookie"].includes(name.toLowerCase())
      );
      const allowed = sameOrigin && methodAllowed && navigationAllowed && !apiDenied && imageAllowed && credentialsAbsent;
      const entry = {
        phase,
        same_origin: sameOrigin,
        method: params.request.method,
        resource_type: params.resourceType,
        allowed
      };
      observed.push(entry);
      if (!allowed) blocked.push(entry);
      void session.send(allowed ? "Fetch.continueRequest" : "Fetch.failRequest", allowed
        ? { requestId: params.requestId }
        : { requestId: params.requestId, errorReason: "BlockedByClient" });
    });
    await Promise.all([
      session.send("Page.enable"),
      session.send("Runtime.enable"),
      session.send("Network.enable"),
      session.send("Fetch.enable", { patterns: [{ urlPattern: "*", requestStage: "Request" }] })
    ]);
    await session.send("Network.clearBrowserCache");
    await session.send("Network.clearBrowserCookies");

    const controlBefore = blocked.length;
    await evaluate(session, `fetch("https://example.invalid/aria-0098-control").catch(() => null)`);
    await new Promise((resolve) => setTimeout(resolve, 100));
    if (blocked.length !== controlBefore + 1 || blocked.at(-1)?.same_origin !== false) {
      throw new Error("0098_NETWORK_BLOCK_CONTROL_FAILED");
    }

    phase = "artifact";
    const pageResults = [];
    for (const pagePath of pagePaths) {
      await navigate(session, `${origin}${pagePath}`);
      const beforeInteractions = observed.length;
      const result = await evaluate(session, `(() => {
        const links = [...document.querySelectorAll("a[href]")].map((item) => item.getAttribute("href"));
        const inputs = [...document.querySelectorAll("input, textarea")];
        for (const input of inputs) {
          input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }));
        }
        for (const button of document.querySelectorAll("button")) button.click();
        return {
          cookie_length: document.cookie.length,
          form_count: document.forms.length,
          links,
          xss_marker: globalThis.__ARIA_0098_XSS__ ?? null,
          framework_inline_script_count: document.querySelectorAll("script:not([src])").length,
          injected_remote_image_count: document.querySelectorAll('img[src*="example.invalid"]').length,
          storage_entries: localStorage.length + sessionStorage.length,
          href: location.href
        };
      })()`);
      await new Promise((resolve) => setTimeout(resolve, 150));
      const normalizedLinks = result.links.map((link) => normalizePagePath(link));
      if (!normalizedLinks.every((link) => allowedPaths.has(link))) {
        throw new Error("0098_BROWSER_NAVIGATION_TARGET_INVALID");
      }
      if (
        result.cookie_length !== 0 ||
        result.form_count !== 0 ||
        result.xss_marker !== null ||
        result.injected_remote_image_count !== 0 ||
        result.storage_entries !== 0
      ) {
        throw new Error("0098_BROWSER_INERTNESS_FAILED");
      }
      const interactionRequests = observed.slice(beforeInteractions).filter((entry) => entry.phase === "artifact");
      if (interactionRequests.some((entry) => entry.method !== "GET" && entry.method !== "HEAD")) {
        throw new Error("0098_BROWSER_SUBMISSION_DETECTED");
      }
      pageResults.push({
        path: pagePath,
        forms: result.form_count,
        links: normalizedLinks.length,
        framework_inline_scripts: result.framework_inline_script_count,
        storage_entries: result.storage_entries
      });
    }

    const artifactBlocked = blocked.filter((entry) => entry.phase === "artifact");
    const artifactWebSockets = websocketAttempts.filter((entry) => entry.phase === "artifact");
    if (artifactBlocked.length || artifactWebSockets.length || runtimeExceptions.includes("artifact")) {
      throw new Error("0098_BROWSER_RUNTIME_POLICY_FAILED");
    }
    return {
      browser: executable.endsWith("msedge.exe") ? "Microsoft Edge" : "Google Chrome",
      network_control_probe: "PASS",
      pages: pageResults,
      artifact_request_count: observed.filter((entry) => entry.phase === "artifact").length,
      blocked_artifact_requests: artifactBlocked.length,
      websocket_attempts: artifactWebSockets.length,
      runtime_exceptions: runtimeExceptions.filter((entry) => entry === "artifact").length
    };
  } finally {
    if (session) {
      try {
        await session.send("Browser.close");
      } catch {
        // Browser.close commonly closes the transport before its response arrives.
      }
      session.close();
    }
    if (browserProcess.exitCode === null) browserProcess.kill();
    await Promise.race([
      new Promise((resolve) => browserProcess.once("exit", resolve)),
      new Promise((resolve) => setTimeout(resolve, 3000))
    ]);
  }
}
