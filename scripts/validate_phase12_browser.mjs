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
const networkFailures = [];
socket.addEventListener("message", (event) => {
  const message = JSON.parse(event.data);
  if (message.id && pending.has(message.id)) {
    const { resolve, reject } = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) reject(new Error(JSON.stringify(message.error)));
    else resolve(message.result);
  }
  if (message.method === "Runtime.exceptionThrown") {
    consoleErrors.push(message.params.exceptionDetails.text);
  }
  if (message.method === "Runtime.consoleAPICalled" && message.params.type === "error") {
    consoleErrors.push(message.params.args.map((item) => item.value ?? item.description).join(" "));
  }
  if (message.method === "Network.loadingFailed" && !message.params.canceled) {
    networkFailures.push(message.params.errorText);
  }
});

function send(method, params = {}) {
  const id = ++sequence;
  socket.send(JSON.stringify({ id, method, params }));
  return new Promise((resolve, reject) => pending.set(id, { resolve, reject }));
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

async function waitFor(expression, label, timeout = 20_000) {
  const started = Date.now();
  while (Date.now() - started < timeout) {
    if (await evaluate(expression)) return;
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error(`Timed out waiting for ${label}.`);
}

async function selectProfile(profileId, displayName) {
  await evaluate(`(() => {
    const selector = document.querySelector('#profile-selector');
    selector.value = ${JSON.stringify(profileId)};
    selector.dispatchEvent(new Event('change', { bubbles: true }));
    return true;
  })()`);
  await waitFor(
    `document.querySelector('h1')?.textContent === ${JSON.stringify(`Doctor Visit Brief — ${displayName}`)} && !document.body.textContent.includes('Assembling trusted records')`,
    `${displayName} brief`,
  );
}

async function openEvidence(cardTitle, itemText = null) {
  await evaluate(`(() => {
    const card = [...document.querySelectorAll('.card')].find(
      (item) => item.querySelector('h2')?.textContent === ${JSON.stringify(cardTitle)}
    );
    const article = ${itemText === null ? "card" : `[...card.querySelectorAll('article')].find((item) => item.textContent.includes(${JSON.stringify(itemText)}))`};
    article.querySelector('button').click();
    return true;
  })()`);
  await waitFor(
    `document.querySelector('.evidence-drawer')?.textContent.includes('fictional-doctor-visit-record.pdf')`,
    `${cardTitle} evidence`,
  );
  const value = await evaluate(`({
    title: ${JSON.stringify(cardTitle)},
    item: ${JSON.stringify(itemText)},
    source: document.querySelector('.evidence-drawer').textContent.includes('fictional-doctor-visit-record.pdf'),
    page: document.querySelector('.evidence-drawer').textContent.includes('Page1')
  })`);
  await evaluate(`document.querySelector('.evidence-drawer button').click()`);
  await waitFor(`!document.querySelector('.evidence-drawer')`, "evidence drawer close");
  return value;
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
await send("Page.navigate", { url: "http://localhost:3000/doctor-visit" });
await waitFor(
  `document.querySelector('#profile-selector') && document.querySelector('#profile-selector').options.length >= 2`,
  "profile selector",
);

await selectProfile("18ad5348-36ba-574b-be47-84d8d2fd3419", "Doctor Visit Demo");
const fullBrief = await evaluate(`(() => {
  const body = document.body.textContent;
  const headings = [...document.querySelectorAll('.doctor-visit-grid h2')].map((item) => item.textContent);
  const changeMetrics = [...document.querySelectorAll('.doctor-visit-change-metrics span')].map((item) => item.textContent);
  const required = ['Known History','Recent Changes','Current Medications','Recent Labs','Recent Measurements','Recent Symptoms','Missing Evidence','Questions to Discuss','Evidence Summary'];
  return {
    title: document.querySelector('h1')?.textContent,
    allSections: required.every((item) => headings.includes(item)),
    history: ['Diabetes','Thyroid condition','Past TB treatment'].every((item) => body.includes(item)),
    medication: body.includes('Metformin') && body.includes('500 mg twice daily oral'),
    labs: body.includes('HbA1c') && body.includes('7.2 %') && body.includes('Fasting glucose') && body.includes('118 mg/dL'),
    symptoms: body.includes('Constipation was reported 3 time(s)'),
    trend: changeMetrics.some((item) => item.includes('172')) && changeMetrics.some((item) => item.includes('148')),
    missing: body.includes('No recent thyroid lab is recorded'),
    question: body.includes('Would updated thyroid testing be useful to discuss?'),
    version: body.includes('doctor-visit-v1'),
    prohibitedAdvice: /you have diabetes|increase metformin|stop taking|change your dose/i.test(body),
  };
})()`);

const evidence = [
  await openEvidence("Known History", "Diabetes"),
  await openEvidence("Current Medications", "Metformin"),
  await openEvidence("Recent Labs", "HbA1c"),
];

await evaluate(`(() => {
  const card = [...document.querySelectorAll('.card')].find((item) => item.querySelector('h2')?.textContent === 'Recent Changes');
  card.querySelector('button').click();
  return true;
})()`);
await waitFor(
  `document.querySelector('.analytics-why')?.textContent.includes('HOW IT WAS CALCULATED')`,
  "analytics WHY drawer",
);
const trendWhy = await evaluate(`(() => {
  const text = document.querySelector('.analytics-why').textContent;
  return {
    periods: text.includes('Personal comparison periods'),
    calculation: text.includes('Recent mean 172 mg/dL minus baseline mean 148 mg/dL'),
    version: text.includes('numeric-trend-v1'),
    evidence: text.includes('145 mg/dL') && text.includes('168 mg/dL'),
  };
})()`);
await evaluate(`document.querySelector('.analytics-why button').click()`);
await waitFor(`!document.querySelector('.analytics-why')`, "analytics drawer close");

await evaluate(`(() => {
  window.__phase12PrintCalled = false;
  window.print = () => { window.__phase12PrintCalled = true; };
  document.querySelector('.doctor-visit-print').click();
  return window.__phase12PrintCalled;
})()`);
const printButton = await evaluate(`window.__phase12PrintCalled`);
await send("Emulation.setEmulatedMedia", { media: "print" });
const printView = await evaluate(`(() => {
  const visible = (selector) => getComputedStyle(document.querySelector(selector)).display !== 'none';
  return {
    sidebarHidden: !visible('.sidebar'),
    navigationHidden: !visible('.top-header'),
    printControlHidden: !visible('.doctor-visit-print'),
    summaryVisible: visible('.doctor-visit-main'),
    allSectionCardsRetained: document.querySelectorAll('.doctor-visit-grid>.card').length === 9,
    evidenceLabelsRetained: visible('.doctor-visit-evidence span'),
  };
})()`);
const pdf = await send("Page.printToPDF", { printBackground: true, preferCSSPageSize: true });
const printScreenshot = await send("Page.captureScreenshot", {
  format: "png",
  captureBeyondViewport: true,
});
await send("Emulation.setEmulatedMedia", { media: "screen" });

mkdirSync(".tmp", { recursive: true });
writeFileSync(".tmp/phase12-doctor-visit.pdf", Buffer.from(pdf.data, "base64"));
writeFileSync(
  ".tmp/phase12-doctor-visit-print.png",
  Buffer.from(printScreenshot.data, "base64"),
);
const screenshot = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true });
writeFileSync(".tmp/phase12-doctor-visit.png", Buffer.from(screenshot.data, "base64"));

await selectProfile("136ccd6d-ddc9-511d-8d80-dabade398a4a", "Doctor Visit Empty Demo");
const emptyBrief = await evaluate(`(() => {
  const body = document.body.textContent;
  return {
    history: body.includes('No known history recorded'),
    changes: body.includes('No supported recent changes'),
    medications: body.includes('No current medications recorded'),
    labs: body.includes('No recent labs recorded'),
    measurements: body.includes('No recent measurements recorded'),
    symptoms: body.includes('No recent symptoms recorded'),
    gaps: body.includes('No structural gaps found'),
    questions: body.includes('No questions generated'),
    inventedDemoValues: body.includes('Metformin') || body.includes('7.2 %') || body.includes('118 mg/dL'),
  };
})()`);
await selectProfile("18ad5348-36ba-574b-be47-84d8d2fd3419", "Doctor Visit Demo");
const finalBrowserUrl = await evaluate("location.href");

console.log(JSON.stringify({
  browserUrl: finalBrowserUrl,
  fullBrief,
  evidence,
  trendWhy,
  printButton,
  printView,
  pdfBytes: Buffer.from(pdf.data, "base64").length,
  emptyBrief,
  consoleErrors,
  networkFailures,
}, null, 2));
socket.close();
