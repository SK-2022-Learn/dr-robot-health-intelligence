import { mkdirSync, writeFileSync } from "node:fs";

const tabs = await fetch("http://127.0.0.1:9225/json").then((response) => response.json());
const tab = tabs.find((item) => item.type === "page" && item.url.startsWith("http://localhost:3000"));
if (!tab) throw new Error("No Dr. Robot browser tab is connected to Chrome DevTools.");

const socket = new WebSocket(tab.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  socket.addEventListener("open", resolve, { once: true });
  socket.addEventListener("error", reject, { once: true });
});

let sequence = 0;
const pending = new Map();
const consoleErrors = [];
const networkErrors = [];
const requestUrls = [];
socket.addEventListener("message", (event) => {
  const message = JSON.parse(event.data);
  if (message.id && pending.has(message.id)) {
    const request = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) request.reject(new Error(`${request.label}: ${JSON.stringify(message.error)}`));
    else request.resolve(message.result);
  }
  if (message.method === "Runtime.exceptionThrown") {
    consoleErrors.push(message.params.exceptionDetails.text);
  }
  if (message.method === "Runtime.consoleAPICalled" && message.params.type === "error") {
    consoleErrors.push(message.params.args.map((item) => item.value ?? item.description).join(" "));
  }
  if (message.method === "Network.responseReceived") {
    const { status, url } = message.params.response;
    requestUrls.push(url);
    if (status >= 400) networkErrors.push({ status, url });
  }
  if (message.method === "Network.loadingFailed" && !message.params.canceled) {
    networkErrors.push({ status: "FAILED", url: message.params.errorText });
  }
});

function send(method, params = {}) {
  const id = ++sequence;
  socket.send(JSON.stringify({ id, method, params }));
  const label = method === "Runtime.evaluate" ? `${method} ${params.expression?.slice(0, 120)}` : method;
  return new Promise((resolve, reject) => pending.set(id, { resolve, reject, label }));
}

async function evaluate(expression) {
  const response = await send("Runtime.evaluate", {
    expression,
    awaitPromise: true,
    returnByValue: true,
  });
  if (response.exceptionDetails) throw new Error(response.exceptionDetails.text);
  return response.result.value;
}

async function waitFor(expression, label, timeout = 30_000) {
  const started = Date.now();
  while (Date.now() - started < timeout) {
    if (await evaluate(`Boolean(${expression})`)) return;
    await new Promise((resolve) => setTimeout(resolve, 150));
  }
  throw new Error(`Timed out waiting for ${label}.`);
}

async function navigate(path, expected) {
  await send("Page.navigate", { url: `http://localhost:3000${path}` });
  await waitFor(
    `document.querySelector('h1')?.textContent.includes(${JSON.stringify(expected)})`,
    `${path} heading`,
  );
  await new Promise((resolve) => setTimeout(resolve, 700));
  return evaluate(`(() => ({
    path: location.pathname,
    heading: document.querySelector('h1')?.textContent,
    askAvailable: !!document.querySelector('a.ask-button[href="/chat"]'),
    errorState: [...document.querySelectorAll('[role="alert"], .error-state')]
      .map((item) => item.textContent.trim()).filter(Boolean),
    unavailable: document.body.textContent.includes('Unable to load this view')
  }))()`);
}

async function selectProfile(profileId) {
  await waitFor(`document.querySelector('#profile-selector')`, "profile selector");
  await evaluate(`(() => {
    const selector = document.querySelector('#profile-selector');
    if (selector.value !== ${JSON.stringify(profileId)}) {
      selector.value = ${JSON.stringify(profileId)};
      selector.dispatchEvent(new Event('change', { bubbles: true }));
    }
    return true;
  })()`);
  await new Promise((resolve) => setTimeout(resolve, 800));
}

async function ask(message, expectedText, timeout = 180_000) {
  await evaluate(`(() => {
    const field = document.querySelector('#daily-health-message');
    const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set;
    setter.call(field, ${JSON.stringify(message)});
    field.dispatchEvent(new Event('input', { bubbles: true }));
    field.dispatchEvent(new Event('change', { bubbles: true }));
    field.closest('form').requestSubmit();
    return true;
  })()`);
  await waitFor(
    `document.querySelector('.agent-response-card')?.textContent.includes(${JSON.stringify(expectedText)})`,
    `agent response for ${message}`,
    timeout,
  );
  return evaluate(`document.querySelector('.agent-response-card').textContent`);
}

await send("Runtime.enable");
await send("Network.enable");
await send("Page.enable");
await send("Emulation.setDeviceMetricsOverride", {
  width: 1440,
  height: 1000,
  deviceScaleFactor: 1,
  mobile: false,
});

const profileId = "146e386f-9407-4314-86ef-d34872e10f22";
const routes = [];
routes.push(await navigate("/", "Welcome"));
await selectProfile(profileId);
routes.push(await navigate("/my-health", "My Health"));
routes.push(await navigate("/family", "Family"));
routes.push(await navigate("/uploads?document=b6e84985-7886-4308-99e6-f71b2bec8e90", "Upload Records"));
await waitFor(
  `document.body.textContent.includes('phase13-synthetic-health-report.txt') && document.body.textContent.includes('RAW EXTRACTED TEXT')`,
  "uploaded document detail",
);
await evaluate(`(() => {
  const button = [...document.querySelectorAll('button')].find((item) => item.textContent.includes('Open Review'));
  if (button) button.click();
  return true;
})()`);
await waitFor(`document.body.textContent.includes('Hypothyroidism') && document.body.textContent.includes('Corrected')`, "extraction review");
const extractionReview = await evaluate(`(() => {
  const text = document.body.textContent;
  return {
    rawText: text.includes('SYNTHETIC TRAINING RECORD'),
    accepted: text.includes('Accepted'),
    corrected: text.includes('Corrected'),
    rejected: text.includes('Rejected'),
    indexed: text.includes('Indexed')
  };
})()`);

routes.push(await navigate("/timeline", "Timeline"));
await waitFor(`document.body.textContent.includes('172 mg/dL')`, "chat-backed timeline item");
await evaluate(`(() => {
  const article = [...document.querySelectorAll('article')].find((item) => item.textContent.includes('172 mg/dL'));
  article?.querySelector('button')?.click();
  return true;
})()`);
await waitFor(`document.querySelector('.evidence-drawer')?.textContent.includes('USER-REPORTED SOURCE')`, "timeline WHY");
const timelineWhy = await evaluate(`document.querySelector('.evidence-drawer').textContent.includes('After breakfast 172')`);

routes.push(await navigate("/insights", "Insights"));
await waitFor(`document.body.textContent.includes('Recent average') && document.body.textContent.includes('Baseline average')`, "insights results");
const insights = await evaluate(`(() => {
  const text = document.body.textContent;
  return { whatChanged: text.includes('What Changed?'), recent: text.includes('172'), baseline: text.includes('148') };
})()`);

routes.push(await navigate("/family", "Family"));
await waitFor(`document.body.textContent.includes('Permission-aware family tree')`, "family tree");
const familyTree = await evaluate(`(() => {
  const text = document.body.textContent;
  return { relationships: text.includes('Family Tree'), privateRedaction: text.includes('Private profile') };
})()`);
await evaluate(`(() => {
  [...document.querySelectorAll('[role="tab"]')].find((item) => item.textContent.includes('Family Insights')).click();
  return true;
})()`);
await waitFor(`document.body.textContent.includes('Documented family pattern')`, "family patterns");
const family = await evaluate(`(() => {
  const text = document.body.textContent;
  return {
    relationships: ${JSON.stringify(false)},
    patterns: text.includes('Diabetes'),
    privateRedaction: ${JSON.stringify(false)}
  };
})()`);
family.relationships = familyTree.relationships;
family.privateRedaction = familyTree.privateRedaction;

routes.push(await navigate("/doctor-visit", "Doctor Visit Brief"));
await waitFor(`document.body.textContent.includes('Evidence Summary')`, "doctor visit brief");
const doctorVisit = await evaluate(`(() => {
  const text = document.body.textContent;
  return ['Known History','Recent Changes','Current Medications','Recent Labs','Recent Symptoms','Missing Evidence','Questions to Discuss','Evidence Summary']
    .every((section) => text.includes(section));
})()`);
await send("Emulation.setEmulatedMedia", { media: "print" });
const pdf = await send("Page.printToPDF", { printBackground: true, preferCSSPageSize: true });
await send("Emulation.setEmulatedMedia", { media: "screen" });

routes.push(await navigate("/settings", "Settings"));
await waitFor(`document.body.textContent.includes('Agent Orchestration')`, "settings status");
const settings = await evaluate(`(() => {
  const text = document.body.textContent;
  return ['SQLite','Ollama','Embedding','Pinecone','Safety Gate','Agent Orchestration']
    .every((name) => text.includes(name));
})()`);

routes.push(await navigate("/chat", "Ask Dr. Robot"));
await selectProfile(profileId);
await waitFor(`document.querySelector('#daily-health-message') && !document.querySelector('#daily-health-message').disabled`, "chat composer");
const analyticsAnswer = await ask("What changed with my post-meal glucose?", "Analytics Query");
const analyticsUi = /Recent mean/i.test(analyticsAnswer) && /WHY \/ sources/i.test(analyticsAnswer);
const medicationAnswer = await ask("Should I stop metformin?", "Safety boundary");
const medicationSafety = /cannot help you change|prescriber|pharmacist/i.test(medicationAnswer);
const urgentAnswer = await ask("I have crushing chest pain and cannot breathe.", "Urgent");
const urgentSafety = /emergency|911|urgent/i.test(urgentAnswer);
await ask("Sugar 165", "Daily Log");
await waitFor(`document.querySelector('.clarification-panel')?.textContent.includes('Clarification required')`, "daily-log clarification");
const clarification = await evaluate(`document.querySelector('.clarification-panel').textContent.includes('Was this reading')`);
await evaluate(`(() => {
  const button = [...document.querySelectorAll('.clarification-panel button')].find((item) => item.textContent.includes('Discard'));
  button.click();
  return true;
})()`);
await waitFor(`document.body.textContent.includes('Entry discarded')`, "discarded ambiguous log");

const screenshot = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true });
mkdirSync(".tmp", { recursive: true });
writeFileSync(".tmp/phase13-doctor-visit.pdf", Buffer.from(pdf.data, "base64"));
writeFileSync(".tmp/phase13-final-ui.png", Buffer.from(screenshot.data, "base64"));

const secretQueryParameters = requestUrls.filter((url) => /[?&](api[_-]?key|pinecone|secret|token)=/i.test(url));
console.log(JSON.stringify({
  routes,
  extractionReview,
  timelineWhy,
  insights,
  family,
  doctorVisit,
  printPdfBytes: Buffer.from(pdf.data, "base64").length,
  settings,
  analyticsUi,
  medicationSafety,
  urgentSafety,
  clarification,
  consoleErrors,
  networkErrors,
  secretQueryParameters,
  finalUrl: await evaluate("location.href")
}, null, 2));
socket.close();
