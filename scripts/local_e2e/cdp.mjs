// Local-only CDP driver. Reads one JSON command per line from stdin and writes
// one JSON response per line. Keeps a single browser profile so auth state
// persists between runs. Used exclusively for isolated local E2E validation.
import { spawn } from "node:child_process";
import fs from "node:fs";
import readline from "node:readline";

const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const PORT = Number(process.env.CDP_PORT || 9444);
const PROFILE = process.env.CDP_PROFILE || "D:/Hackathon/Hack the vibe/CivicFlow/.cache/local_e2e/chrome-profile";
fs.mkdirSync(PROFILE, { recursive: true });

const proc = spawn(CHROME, [
  "--headless=new", "--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage",
  "--hide-scrollbars", "--no-first-run", "--no-default-browser-check",
  "--no-proxy-server", "--disable-features=BlockInsecurePrivateNetworkRequests",
  `--remote-debugging-port=${PORT}`, `--user-data-dir=${PROFILE}`,
  "--window-size=1440,900", "about:blank",
], { stdio: "ignore" });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let target;
for (let i = 0; i < 60; i++) {
  await sleep(250);
  try {
    const list = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json();
    target = list.find((t) => t.type === "page");
    if (target) break;
  } catch {}
}
if (!target) { console.log(JSON.stringify({ error: "NO_TARGET" })); proc.kill(); process.exit(1); }

const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((r) => (ws.onopen = r));
let id = 0;
const pending = new Map();
ws.addEventListener("message", (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
});
function call(method, params = {}) {
  const myId = ++id;
  return new Promise((resolve) => {
    pending.set(myId, resolve);
    ws.send(JSON.stringify({ id: myId, method, params }));
  });
}
await call("Page.enable");
await call("Runtime.enable");
await call("Network.enable");
const netFailures = [];
const requestUrls = [];
await call("Log.enable");
ws.addEventListener("message", (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.method === "Log.entryAdded") {
    netFailures.push({ log: msg.params?.entry?.text, source: msg.params?.entry?.source });
  }
  if (msg.method === "Runtime.consoleAPICalled") {
    netFailures.push({ console: (msg.params?.args || []).map((a) => a.value || a.description).join(" ") });
  }
  if (msg.method === "Network.loadingFailed") {
    netFailures.push({ url: msg.params?.requestId, error: msg.params?.errorText });
  }
  if (msg.method === "Network.requestWillBeSent") {
    const requestUrl = msg.params?.request?.url || "";
    requestUrls.push(requestUrl);
    if (/54321|5432/.test(requestUrl)) {
      netFailures.push({ url: requestUrl, stage: "sent" });
    }
  }
});

async function evaluate(expression, awaitPromise = false) {
  const res = await call("Runtime.evaluate", {
    expression, returnByValue: true, awaitPromise, userGesture: true,
  });
  if (res.result?.exceptionDetails) {
    return { error: res.result.exceptionDetails.text || "eval exception" };
  }
  return res.result?.result?.value;
}

const fillScript = (selector, value) => `(() => {
  const el = document.querySelector(${JSON.stringify(selector)});
  if (!el) return { ok:false, reason:'not found' };
  const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype
    : el instanceof HTMLSelectElement ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
  setter.call(el, ${JSON.stringify(value)});
  el.dispatchEvent(new Event('input', { bubbles: true }));
  el.dispatchEvent(new Event('change', { bubbles: true }));
  return { ok:true, value:el.value };
})()`;

async function handle(cmd) {
  switch (cmd.op) {
    case "viewport":
      await call("Emulation.setDeviceMetricsOverride", {
        width: cmd.w, height: cmd.h, deviceScaleFactor: 1, mobile: cmd.mobile === true,
      });
      return { ok: true };
    case "nav": {
      await call("Page.navigate", { url: cmd.url });
      await sleep(cmd.wait || 2500);
      return { ok: true, url: await evaluate("location.href") };
    }
    case "wait":
      await sleep(cmd.ms || 1000);
      return { ok: true };
    case "eval":
      return { value: await evaluate(cmd.expression, cmd.await === true) };
    case "fill":
      return { value: await evaluate(fillScript(cmd.selector, cmd.value)) };
    case "fillnth":
      return { value: await evaluate(`(() => {
        const els = [...document.querySelectorAll(${JSON.stringify(cmd.selector)})];
        const el = els[${cmd.index || 0}];
        if (!el) return { ok:false, reason:'not found', count: els.length };
        const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype
          : el instanceof HTMLSelectElement ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
        Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, ${JSON.stringify(cmd.value)});
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        return { ok:true, value: el.value };
      })()`) };
    case "click":
      return { value: await evaluate(`(() => { const e=document.querySelector(${JSON.stringify(cmd.selector)}); if(!e) return {ok:false,reason:'not found'}; e.click(); return {ok:true}; })()`) };
    case "select":
      return { value: await evaluate(fillScript(cmd.selector, cmd.value)) };
    case "press":
      return { value: await evaluate(`(() => { const e=document.querySelector(${JSON.stringify(cmd.selector)}); if(!e) return {ok:false}; e.focus(); e.dispatchEvent(new KeyboardEvent('keydown',{key:${JSON.stringify(cmd.key)},bubbles:true})); e.dispatchEvent(new KeyboardEvent('keypress',{key:${JSON.stringify(cmd.key)},bubbles:true})); return {ok:true}; })()`) };
    case "clicktext": {
      const target = cmd.tag || "button";
      return { value: await evaluate(`(() => {
        const els = [...document.querySelectorAll(${JSON.stringify(target)})];
        const el = els.find((e) => e.innerText.trim() === ${JSON.stringify(cmd.text)});
        if (!el) return { ok:false, reason:'not found', seen: els.map(e=>e.innerText.trim()).slice(0,20) };
        el.click(); return { ok:true };
      })()`) };
    }
    case "text":
      return { value: await evaluate(`document.querySelector(${JSON.stringify(cmd.selector)})?.innerText ?? null`) };
    case "body":
      return { value: await evaluate(`document.body.innerText.slice(0, ${cmd.limit || 6000})`) };
    case "url":
      return { value: await evaluate("location.href") };
    case "netfail":
      return { value: netFailures.slice(-20) };
    case "requests": {
      const limit = typeof cmd.limit === "number" ? cmd.limit : 40;
      return { value: requestUrls.slice(-limit) };
    }
    case "block": {
      await call("Network.setBlockedURLs", { urls: cmd.urls || [] });
      return { ok: true };
    }
    case "cookies": {
      const res = await call("Network.getCookies", cmd.url ? { urls: [cmd.url] } : {});
      return { value: (res.result?.cookies || []).map((c) => ({
        name: c.name, value: c.value, domain: c.domain, path: c.path, expires: c.expires,
      })) };
    }
    case "setcookie": {
      await call("Network.setCookie", {
        name: cmd.name, value: cmd.value, domain: cmd.domain || "127.0.0.1",
        path: cmd.path || "/", url: cmd.url || undefined,
      });
      return { ok: true };
    }
    case "shot": {
      const shot = await call("Page.captureScreenshot", { format: "png", captureBeyondViewport: false, fromSurface: true });
      fs.writeFileSync(cmd.path, Buffer.from(shot.result.data, "base64"));
      return { ok: true, bytes: fs.statSync(cmd.path).size };
    }
    case "clear": {
      const res = await evaluate(`(() => { localStorage.clear(); sessionStorage.clear(); return true; })()`);
      return { ok: true, res };
    }
    default:
      return { error: `unknown op ${cmd.op}` };
  }
}

const rl = readline.createInterface({ input: process.stdin });
for await (const line of rl) {
  if (!line.trim()) continue;
  try {
    const cmd = JSON.parse(line);
    const result = await handle(cmd);
    process.stdout.write(JSON.stringify(result) + "\n");
  } catch (e) {
    process.stdout.write(JSON.stringify({ error: String(e) }) + "\n");
  }
}
ws.close();
proc.kill();
