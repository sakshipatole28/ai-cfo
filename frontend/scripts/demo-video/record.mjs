// Records a narrated walkthrough of the console (synthetic data) as an MP4.
//
//   npm run build:preview
//   DEMO_FFMPEG=/path/to/ffmpeg DEMO_PIPER_PY=/path/to/python DEMO_VOICE=/path/to/voice.onnx \
//     node scripts/demo-video/record.mjs <out_dir>
//
// Narration is generated offline with Piper; captions on screen repeat what is said.
import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync, readdirSync, renameSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";

import { chromium } from "@playwright/test";

const OUT = resolve(process.argv[2] ?? "demo-video-out");
const FFMPEG = process.env.DEMO_FFMPEG ?? "ffmpeg";
const PY = process.env.DEMO_PIPER_PY ?? "python3";
const VOICE = process.env.DEMO_VOICE;
const FAST = process.env.DEMO_FAST === "1"; // rehearsal: checks every click quickly, no video
const APP = "file://" + resolve("dist-preview/index.html");
const W = 1440, H = 900;
mkdirSync(OUT, { recursive: true });

/* ------------------------------------------------------------------ helpers */
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const OVERLAY = () => {
  if (document.getElementById("demo-cap")) return;
  const css = document.createElement("style");
  css.textContent = `
  #demo-cap{position:fixed;left:288px;bottom:22px;width:min(760px,calc(100vw - 320px));z-index:2147483646;pointer-events:none;
    background:rgba(6,22,28,.93);color:#f2fbf9;border-radius:16px;padding:14px 18px 15px;font:15px/1.5 "Geist Variable",system-ui,sans-serif;
    box-shadow:0 18px 40px -12px rgba(0,0,0,.45);border:1px solid rgba(94,230,193,.35);transition:opacity .25s}
  #demo-cap .k{font-size:11.5px;letter-spacing:.08em;text-transform:uppercase;color:#7ff0d0;font-weight:600}
  #demo-cap .t{font:600 18px/1.3 "Bricolage Grotesque Variable","Geist Variable",sans-serif;margin-top:2px}
  #demo-cap .s{margin-top:4px;color:#cfe6e4}
  #demo-cur{position:fixed;left:-40px;top:-40px;width:22px;height:22px;margin:-11px 0 0 -11px;border-radius:50%;z-index:2147483647;pointer-events:none;
    background:rgba(56,182,255,.35);border:2px solid #0b6fb8;box-shadow:0 0 0 4px rgba(255,255,255,.7);transition:left .65s cubic-bezier(.3,.7,.2,1),top .65s cubic-bezier(.3,.7,.2,1)}
  #demo-ring{position:fixed;z-index:2147483645;pointer-events:none;border:3px solid #38b6ff;border-radius:12px;box-shadow:0 0 0 6px rgba(56,182,255,.22);opacity:0;transition:all .35s}
  .demo-ripple{position:fixed;width:16px;height:16px;margin:-8px 0 0 -8px;border-radius:50%;border:3px solid #38b6ff;z-index:2147483647;pointer-events:none;animation:dr .6s ease-out forwards}
  @keyframes dr{to{transform:scale(3.4);opacity:0}}
  #demo-card{position:fixed;inset:0;z-index:2147483647;display:flex;align-items:center;justify-content:center;pointer-events:none;
    background:radial-gradient(60% 90% at 8% 0%,rgba(94,230,193,.55),transparent 60%),radial-gradient(55% 80% at 100% 10%,rgba(56,182,255,.45),transparent 62%),#f1f7f6}
  #demo-card .in{max-width:860px;padding:0 40px;color:#0a1f24;font-family:"Geist Variable",system-ui,sans-serif}
  #demo-card h1{font:700 54px/1.05 "Bricolage Grotesque Variable",sans-serif;letter-spacing:-.025em;margin:16px 0 14px}
  #demo-card p{font-size:20px;color:#2c4750;margin:0}
  #demo-card .logo{width:56px;height:56px;border-radius:16px;background:linear-gradient(135deg,#5ee6c1,#38b6ff)}`;
  document.head.append(css);
  const cap = Object.assign(document.createElement("div"), { id: "demo-cap" });
  cap.innerHTML = '<div class="k"></div><div class="t"></div><div class="s"></div>';
  const cur = Object.assign(document.createElement("div"), { id: "demo-cur" });
  const ring = Object.assign(document.createElement("div"), { id: "demo-ring" });
  document.body.append(cap, cur, ring);
};

async function ensureOverlay(p) {
  await p.evaluate(OVERLAY);
}

async function caption(p, chapter, title, text, left) {
  await ensureOverlay(p);
  await p.evaluate(
    ([k, t, s, l]) => {
      const c = document.getElementById("demo-cap");
      c.querySelector(".k").textContent = k;
      c.querySelector(".t").textContent = t;
      c.querySelector(".s").textContent = s;
      c.style.left = l;
      if (window.innerWidth < 600) Object.assign(c.style, { bottom: "auto", top: "92px", width: "calc(100vw - 24px)", fontSize: "13.5px" });
    },
    [chapter, title, text, left ?? (p.viewportSize().width < 600 ? "12px" : "288px")],
  );
}

async function card(p, show, title = "", sub = "") {
  await p.evaluate(
    ([on, t, s]) => {
      document.getElementById("demo-card")?.remove();
      if (!on) return;
      const d = Object.assign(document.createElement("div"), { id: "demo-card" });
      d.innerHTML = `<div class="in"><div class="logo"></div><h1></h1><p></p></div>`;
      d.querySelector("h1").textContent = t;
      d.querySelector("p").textContent = s;
      document.body.append(d);
    },
    [show, title, sub],
  );
}

async function point(p, locator, { click = true, ring = true } = {}) {
  await locator.scrollIntoViewIfNeeded().catch(() => {});
  const box = await locator.boundingBox();
  if (!box) return;
  const x = box.x + box.width / 2, y = box.y + box.height / 2;
  await p.evaluate(
    ([x, y, b, r]) => {
      const c = document.getElementById("demo-cur");
      c.style.left = `${x}px`;
      c.style.top = `${y}px`;
      const g = document.getElementById("demo-ring");
      if (r) Object.assign(g.style, { left: `${b.x - 6}px`, top: `${b.y - 6}px`, width: `${b.width + 12}px`, height: `${b.height + 12}px`, opacity: 1 });
    },
    [x, y, box, ring],
  );
  await sleep(750);
  if (click) {
    await p.evaluate(([x, y]) => {
      const r = Object.assign(document.createElement("div"), { className: "demo-ripple" });
      Object.assign(r.style, { left: `${x}px`, top: `${y}px` });
      document.body.append(r);
      setTimeout(() => r.remove(), 700);
    }, [x, y]);
    await locator.click();
  }
  await sleep(250);
  await p.evaluate(() => {
    document.getElementById("demo-ring").style.opacity = 0;
  });
}

async function scrollMain(p, by) {
  await p.evaluate((by) => document.querySelector("main")?.scrollBy({ top: by, behavior: "smooth" }), by);
  await sleep(700);
}

async function signIn(p, who = "Priya Anand") {
  await point(p, p.getByRole("button", { name: new RegExp(who) }).first());
  await point(p, p.getByRole("button", { name: "Continue" }));
  await p.locator("#totp").pressSequentially("482913", { delay: 90 });
  await sleep(1500);
  await p.evaluate(() => document.querySelectorAll("[data-sonner-toast]").forEach((t) => { t.style.visibility = "hidden"; }));
}

const nav = (p, name) => point(p, p.getByRole("link", { name: new RegExp(`^${name}`) }).first());

/* ------------------------------------------------------------------ scenes */
// Each scene: [id, chapter, title, narration, action]. Narration is spoken; title + narration are shown.
const DESKTOP = [
  ["intro", "", "", "Welcome. This is a short guided tour of A I C F O, a tool for chartered accountants, investment advisers and mutual fund distributors. Everything you will see uses made-up clients and fictional fund names.",
    async (p) => { await card(p, true, "AI CFO", "Every number computed. Every claim cited. Every action recorded. A guided tour with fictional data."); }],
  ["signin", "Sign in", "Each person signs in safely", "Each person in the firm signs in with a password and a six digit code from their phone. There are four roles: owner, adviser, analyst and compliance. Each role sees only what it should.",
    async (p) => { await card(p, false); await sleep(400); await point(p, p.locator("#root").getByText("Demo accounts, one per role"), { click: false }); }],
  ["unlock", "Sign in", "Client names stay private", "Client names and tax numbers are encrypted. They are unlocked only inside this browser, never on our servers.",
    async (p) => { await signIn(p); }],
  ["today", "Today", "What needs attention today", "The Today screen shows what needs attention: reviews waiting for approval, clients due for a review, and how fresh the data is.",
    async (p) => { await point(p, p.locator("#root").getByText("Awaiting approval").first(), { click: false }); }],
  ["actions", "Today", "Next best actions", "Actions are ranked by importance, such as approving a review, reconnecting a broker, or checking a difference between two data sources.",
    async (p) => { await point(p, p.locator("#root").getByText("Next best actions"), { click: false }); }],
  ["taxcal", "Today", "Tax calendar", "The tax calendar lists purchases that turn long-term in the next thirty days, when the tax rate on the gain falls from twenty to twelve and a half percent.",
    async (p) => { await point(p, p.locator("#root").getByText("Tax calendar"), { click: false }); }],
  ["clients", "Clients", "Every client at a glance", "The client list shows each portfolio, how far it is from its agreed target, and how many draft findings are waiting.",
    async (p) => { await nav(p, "Clients"); }],
  ["client", "Client page", "One client's full picture", "This is one client's full picture, combined from monthly statements and from his broker account. The coloured bar shows where the data came from, and how recent it is.",
    async (p) => { await point(p, p.locator("#root").getByText("Rohan Deshpande").first()); await sleep(600); await point(p, p.locator("#root").getByText("Data coverage by source"), { click: false }); }],
  ["alloc", "Client page", "Is the money split as agreed?", "Here is the split between shares, bonds, gold and cash, against the agreed target. Shares are fourteen points above target, about four lakh rupees.",
    async (p) => { await point(p, p.locator("#root").getByText("Drift", { exact: true }).first(), { click: false }); }],
  ["explain", "Explainable numbers", "Every number explains itself", "Every highlighted number can be opened. It shows the formula, the inputs with their sources, each step of the calculation, and the rule it relies on. Code calculates it, not A I.",
    async (p) => { await point(p, p.getByTitle("Show how this number was calculated").first()); await sleep(1800); await p.evaluate(() => document.querySelector('[role="dialog"] .overflow-y-auto')?.scrollBy({ top: 420, behavior: "smooth" })); }],
  ["holdings", "Client page", "Holdings and each purchase", "Holdings lists every fund and share with its I S I N, value and gain. Opening one shows each purchase and when it becomes long-term.",
    async (p) => { await p.keyboard.press("Escape"); await sleep(400); await point(p, p.getByRole("tab", { name: "Holdings" })); await sleep(500); await point(p, p.locator("tbody tr").first()); }],
  ["lookthrough", "Client page", "What the client really owns", "Look-through opens up every fund to show which companies the client really owns. One bank is almost fourteen percent of everything.",
    async (p) => { await p.keyboard.press("Escape"); await sleep(400); await point(p, p.getByRole("tab", { name: "Look-through" })); }],
  ["overlap", "Client page", "How similar are the funds?", "Overlap shows how similar the funds are. These two funds share sixty nine percent of their holdings, so the second one adds little.",
    async (p) => { await point(p, p.getByRole("tab", { name: "Overlap" })); await sleep(500); await point(p, p.getByRole("button", { name: "69%" }).first()); }],
  ["tax", "Client page", "Tax position", "The tax view shows how much of this year's one lakh twenty five thousand rupee tax-free allowance is left, and every purchase with the date it becomes long-term.",
    async (p) => { await point(p, p.getByRole("tab", { name: "Tax" })); }],
  ["live1", "Live broker connection", "The main feature", "Now the main feature: a live, read-only connection to the client's broker. The client signs in on Dhan's own website. We never see their password.",
    async (p) => { await point(p, p.getByRole("button", { name: "See how the client connects" })); }],
  ["live2", "Live broker connection", "View only, approved by the client", "Dhan asks the client to approve view-only access. Placing orders is impossible.",
    async (p) => { await point(p, p.getByRole("button", { name: /Continue to Dhan/ })); await sleep(400); await p.locator("#dhan-code").pressSequentially("135790", { delay: 90 }); }],
  ["live3", "Live broker connection", "Read, compare, discard", "We use a twenty four hour pass once, read the holdings, compare them with the statement, and throw the pass away. Here one difference was found and sent to the adviser to check.",
    async (p) => { await point(p, p.getByRole("button", { name: /Approve read-only/ })); await sleep(5200); }],
  ["agents1", "AI agents", "The review runs in steps", "Run review starts the A I agents. First, tested code computes every number. Then three analyst agents work in parallel, on overlap, allocation and tax.",
    async (p) => { await point(p, p.getByRole("button", { name: "Done" })); await sleep(300); await point(p, p.getByRole("button", { name: "Run review" })); }],
  ["agents2", "AI agents", "Explained, checked, verified", "A writer agent explains each finding and quotes the rule. A compliance judge and a verifier reject advice-like wording, and any number the code did not produce.",
    async (p) => { await sleep(2500); await p.evaluate(() => document.querySelector('[role="dialog"] .overflow-y-auto')?.scrollBy({ top: 520, behavior: "smooth" })); }],
  ["inbox1", "Review inbox", "The adviser decides", "The review inbox is where the adviser decides. Each draft shows the calculated numbers, the rule it cites, and the result of every compliance check.",
    async (p) => { await p.keyboard.press("Escape"); await sleep(400); await nav(p, "Review inbox"); }],
  ["inbox2", "Review inbox", "Reasoning is recorded", "The adviser adds their reasoning, which is kept as the record of advice, and accepts or dismisses each finding.",
    async (p) => {
      const note = p.locator("textarea").first();
      await point(p, note);
      await note.pressSequentially("Discussed on the call; client agrees to rebalance gradually.", { delay: 25 });
      await p.locator("h2").first().click();
      for (let i = 0; i < 5; i++) { await p.keyboard.press("a"); await sleep(450); }
      await p.evaluate(() => document.querySelectorAll("[data-sonner-toast]").forEach((t) => { t.style.visibility = "hidden"; }));
    }],
  ["inbox3", "Review inbox", "Preview, then approve", "Before approving, the adviser previews the client report with the firm's branding. Only then does anything reach the client.",
    async (p) => { await point(p, p.getByRole("button", { name: "Preview" })); await sleep(1600); await point(p, p.getByRole("button", { name: /Approve and finalise/ })); }],
  ["agentspage", "Agents", "How well the AI performs", "The agents page shows how the system works and how well it performs, including retrieval accuracy, the classifier score, and zero unsupported numbers.",
    async (p) => { await p.evaluate(() => document.querySelectorAll("[data-sonner-toast]").forEach((t) => { t.style.visibility = "hidden"; })); await nav(p, "Agents"); await sleep(600); await point(p, p.locator("#root").getByText("Unsupported numbers").first(), { click: false }); }],
  ["rag1", "Ask the rulebook", "Answers with sources", "Ask the rulebook answers questions only from official sources such as Sebi and the Income Tax Act, and shows exactly which source it used.",
    async (p) => { await nav(p, "Ask the rulebook"); await sleep(400); await point(p, p.getByRole("button", { name: /1.25 lakh LTCG/ })); }],
  ["rag2", "Ask the rulebook", "No buy or sell tips", "Requests for buy or sell tips are refused. The decision always stays with the registered professional.",
    async (p) => { await point(p, p.getByRole("button", { name: /buy more Reliance/ })); }],
  ["copilot", "Copilot", "Ask about a client", "The copilot answers questions about a client using the same calculations, and shows which tools it used.",
    async (p) => { await point(p, p.getByRole("button", { name: /Ask Copilot/ }).first()); await sleep(400); await point(p, p.getByRole("button", { name: "Which funds overlap the most?" })); await sleep(1200); }],
  ["data", "Data inbox", "Data in, checked", "The data inbox shows live broker connections, statement imports with their checks, and any differences between sources, which the team resolves with a click.",
    async (p) => { await p.keyboard.press("Escape"); await sleep(300); await nav(p, "Data inbox"); await sleep(500); await scrollMain(p, 420); await point(p, p.getByRole("button", { name: /Dhan API/ })); }],
  ["access", "Client access", "Clients stay in control", "Clients approve every access request from their own portal. The firm sees requests, consents, and anything clients have shared themselves.",
    async (p) => { await p.evaluate(() => document.querySelectorAll("[data-sonner-toast]").forEach((t) => { t.style.visibility = "hidden"; })); await nav(p, "Client access"); }],
  ["anon", "Share without identities", "Data without names", "Firms can share data without identities. It runs in the browser: names, tax numbers, phone numbers and emails are removed, and accounts become codes made with the firm's own secret key.",
    async (p) => { await nav(p, "Share without identities"); await sleep(400); await point(p, p.getByRole("button", { name: /Remove identities/ })); await sleep(500); await scrollMain(p, 520); }],
  ["team", "Team", "Roles and devices", "The owner manages the team: roles, invitations, suspensions, and every signed-in device.",
    async (p) => { await nav(p, "Team"); }],
  ["audit", "Audit trail", "Tamper-evident record", "Every action is recorded in a tamper-evident log. Verify chain checks that nothing has been changed.",
    async (p) => { await nav(p, "Audit trail"); await sleep(300); await point(p, p.getByRole("button", { name: /Verify chain/ })); await sleep(1100); }],
  ["settings", "Settings", "One switch for AI", "Settings include one switch that turns off every A I feature for the whole firm at once.",
    async (p) => { await nav(p, "Settings"); await sleep(300); await point(p, p.locator("#ai-switch")); await sleep(900); await point(p, p.locator("#ai-switch")); await p.evaluate(() => document.querySelectorAll("[data-sonner-toast]").forEach((t) => { t.style.visibility = "hidden"; })); }],
  ["guide", "How it works", "Plain-language guide", "The guide explains the whole workflow, and more than fifty financial terms, in plain language.",
    async (p) => { await nav(p, "How it works"); await sleep(400); await scrollMain(p, 500); }],
  ["signout", "Sign out", "Signing out", "Signing out clears the keys from this browser.",
    async (p) => { await point(p, p.getByRole("button", { name: "Account menu" })); await sleep(400); await point(p, p.getByRole("menuitem", { name: "Sign out" })); }],
  ["portal1", "Client portal", "The client's own portal", "Clients have their own simple portal. They sign in with a one-time code and see exactly who can view their portfolio.",
    async (p) => {
      await point(p, p.getByRole("tab", { name: /client/i }));
      await point(p, p.getByRole("button", { name: /Send code/ }));
      await p.locator("#client-otp").pressSequentially("246810", { delay: 80 });
      await point(p, p.getByRole("button", { name: /Verify/ }));
    }],
  ["portal2", "Client portal", "Approve with a one-time code", "Each request from the firm shows who is asking, why, what they will see and for how long. The client approves it with a one-time code.",
    async (p) => { await point(p, p.getByRole("button", { name: "Approve" }).first()); await sleep(500); await point(p, p.getByRole("button", { name: /Confirm/ })); }],
  ["portal3", "Client portal", "Share with an accountant", "Clients can also share a read-only view with their accountant, with an expiry date, and revoke it at any time.",
    async (p) => {
      await point(p, p.getByRole("button", { name: /Share with someone else/ }));
      await p.locator("#share-name").pressSequentially("R. Mehta and Co", { delay: 40 });
      await p.locator("#share-email").pressSequentially("filings@mehtaco.example", { delay: 30 });
      await point(p, p.getByRole("button", { name: /Share read-only view/ }));
    }],
];

const MOBILE = [
  ["mobile1", "On a phone", "Works on phones and tablets", "It also works on phones and tablets. Here an adviser signs in and sees only their own clients.",
    async (p) => { await signIn(p, "Arun Kumar"); }],
  ["mobile2", "On a phone", "Everything within reach", "The bottom bar keeps the review inbox, clients and the copilot one tap away.",
    async (p) => { await point(p, p.getByRole("link", { name: /Inbox/ }).last()); await sleep(900); }],
];

const OUTRO = [
  ["outro", "", "", "A I C F O. Every number computed, every claim cited, every action recorded, and a professional always in control. Thank you for watching.",
    async (p) => { await card(p, true, "Thank you", "AI CFO · Portfolio reviews your clients can trust · Demo built with fictional data"); }],
];

/* ------------------------------------------------------------------ narration */
const all = [...DESKTOP, ...MOBILE, ...OUTRO];
const lines = Object.fromEntries(all.map(([id, , , say]) => [id, say]));
const AUDIO = join(OUT, "audio");
const linesJson = JSON.stringify(lines, null, 1);
const cached = (() => { try { return readFileSync(join(OUT, "lines.json"), "utf8") === linesJson && readFileSync(join(AUDIO, "durations.json"), "utf8"); } catch { return false; } })();
writeFileSync(join(OUT, "lines.json"), linesJson);
if (!cached && !FAST) {
  if (!VOICE) throw new Error("Set DEMO_VOICE to a Piper voice .onnx file");
  execFileSync(PY, [resolve("scripts/demo-video/tts.py"), VOICE, join(OUT, "lines.json"), AUDIO], { stdio: "inherit" });
}
const dur = FAST ? Object.fromEntries(Object.keys(lines).map((k) => [k, 0])) : JSON.parse(readFileSync(join(AUDIO, "durations.json"), "utf8"));

/* ------------------------------------------------------------------ record */
const browser = await chromium.launch();

async function segment(name, scenes, viewport, dark = false) {
  const dir = join(OUT, `raw-${name}`);
  const ctx = await browser.newContext({ viewport, colorScheme: dark ? "dark" : "light", ...(FAST ? {} : { recordVideo: { dir, size: viewport } }) });
  const p = await ctx.newPage();
  let scene = "start";
  p.on("console", (m) => m.type() === "error" && console.error(`[${scene}] console error: ${m.text().slice(0, 600)}`));
  p.on("pageerror", (e) => console.error(`page error: ${e.message}\n${(e.stack ?? "").split("\n").slice(0, 4).join("\n")}`));
  const t0 = Date.now();
  await p.goto(APP);
  await ensureOverlay(p);
  await p.evaluate(() => { document.getElementById("demo-cap").style.opacity = 0; });
  await sleep(600);
  const cues = [];
  for (const [id, chapter, title, say, act] of scenes) {
    scene = id;
    const start = Date.now() - t0;
    cues.push({ id, at: start });
    if (title) await caption(p, chapter, title, say);
    else await p.evaluate(() => { const c = document.getElementById("demo-cap"); if (c) c.style.opacity = 0; }).catch(() => {});
    if (title) await p.evaluate(() => { document.getElementById("demo-cap").style.opacity = 1; });
    try {
      await act(p);
    } catch (err) {
      await p.screenshot({ path: join(OUT, `failed-${id}.png`) });
      throw new Error(`scene "${id}" failed: ${err.message.split("\n")[0]}`);
    }
    const need = dur[id] + 900;
    const spent = Date.now() - t0 - start;
    if (spent < need) await sleep(need - spent);
  }
  await sleep(800);
  const total = Date.now() - t0;
  await ctx.close();
  if (FAST) { console.log(`rehearsal ok: ${name} (${scenes.length} scenes)`); return { name, cues, total }; }
  const webm = readdirSync(dir).find((f) => f.endsWith(".webm"));
  renameSync(join(dir, webm), join(OUT, `${name}.webm`));
  return { name, cues, total };
}

const segs = [];
segs.push(await segment("desktop", DESKTOP, { width: W, height: H }));
segs.push(await segment("mobile", MOBILE, { width: 390, height: 844 }));
segs.push(await segment("outro", OUTRO, { width: W, height: H }));
await browser.close();
if (FAST) process.exit(0);

/* ------------------------------------------------------------------ mux */
const parts = [];
for (const s of segs) {
  const inputs = ["-i", join(OUT, `${s.name}.webm`)];
  const filters = [];
  s.cues.forEach((c, i) => {
    inputs.push("-i", join(AUDIO, `${c.id}.wav`));
    filters.push(`[${i + 1}:a]adelay=${c.at}|${c.at},aresample=48000[a${i}]`);
  });
  const mix = s.cues.map((_, i) => `[a${i}]`).join("") + `amix=inputs=${s.cues.length}:normalize=0,apad[aout]`;
  const video = s.name === "mobile"
    ? `[0:v]scale=-2:${H},pad=${W}:${H}:(ow-iw)/2:0:color=0xf1f7f6,setsar=1,fps=30[vout]`
    : `[0:v]scale=${W}:${H},setsar=1,fps=30[vout]`;
  const out = join(OUT, `${s.name}.mp4`);
  execFileSync(FFMPEG, ["-y", "-loglevel", "error", ...inputs, "-filter_complex", [...filters, mix, video].join(";"),
    "-map", "[vout]", "-map", "[aout]", "-t", String(s.total / 1000), "-c:v", "libx264", "-preset", "medium", "-crf", "22",
    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", out], { stdio: "inherit" });
  parts.push(out);
}
const list = join(OUT, "parts.txt");
writeFileSync(list, parts.map((f) => `file '${f}'`).join("\n"));
execFileSync(FFMPEG, ["-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", list, "-c", "copy", "-movflags", "+faststart", join(OUT, "ai-cfo-demo.mp4")], { stdio: "inherit" });

// Chapters for the meeting script / video description
let offset = 0;
const chapters = [];
for (const s of segs) {
  let last = "";
  for (const c of s.cues) {
    const scene = all.find((x) => x[0] === c.id);
    if (scene[1] && scene[1] !== last) {
      const t = Math.round((offset + c.at) / 1000);
      chapters.push(`${String(Math.floor(t / 60)).padStart(2, "0")}:${String(t % 60).padStart(2, "0")} ${scene[1]}`);
      last = scene[1];
    }
  }
  offset += s.total;
}
writeFileSync(join(OUT, "chapters.txt"), chapters.join("\n") + "\n");
console.log(`Done: ${join(OUT, "ai-cfo-demo.mp4")} (${Math.round(offset / 1000)} s)`);
console.log(chapters.join("\n"));
