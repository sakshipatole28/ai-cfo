// Offline-demo check (no API needed): the path the Netlify site takes without VITE_API_URL.
// Create a firm → invite an Admin → the Admin joins with the code → the Admin can grant staff roles only.
// Usage: npm run build:preview && npm run e2e:demo
import { chromium } from "@playwright/test";

const file = "file://" + process.cwd() + "/dist-preview/index.html"; // the single-file preview build
const b = await chromium.launch();
const p = await (await b.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
p.setDefaultTimeout(10000);
let failed = 0; // count failed checks so CI can fail the build
const ok = (n, v) => {
  console.log(`${v ? "PASS" : "FAIL"}  ${n}`);
  if (!v) failed += 1;
};
await p.goto(file);
await p.getByRole("button", { name: /Create a firm account/ }).click();
await p.getByLabel("Firm name").fill("Demo Wealth LLP");
await p.getByLabel("Your full name").fill("Olive Owner");
await p.getByLabel(/Work email/).fill("olive@demo.example");
await p.getByLabel(/^Password/).fill("correct horse battery");
await p.getByRole("button", { name: "Create firm" }).click();
await p.locator("#totp").fill("123456");
await p.getByText("Demo Wealth LLP").first().waitFor();
ok("Owner created firm (demo)", true);
await p.getByRole("link", { name: "Team" }).first().click();
ok("new firm starts with only the Owner", (await p.locator("table").first().locator("tbody tr").count()) === 1);
await p.getByRole("button", { name: /Invite someone/ }).click();
await p.locator("#inv-name").fill("Asha Admin");
await p.locator("#inv-email").fill("asha@demo.example");
await p.getByRole("button", { name: /^Admin/ }).click();
await p.getByRole("button", { name: "Create invite" }).click();
const code = (await p.locator("code").first().innerText()).trim();
ok("invite code shown", /^[0-9A-F]{4}-[0-9A-F]{4}$/.test(code));
await p.getByRole("button", { name: "Done" }).click();
await p.getByRole("button", { name: "Account menu" }).click();
await p.getByRole("menuitem", { name: "Sign out" }).click();
await p.getByRole("button", { name: /Join with an invite code/ }).click();
await p.getByLabel("Invite code").fill(code);
await p.getByLabel("Your full name").fill("Asha Admin");
await p.getByLabel(/Work email/).fill("asha@demo.example");
await p.getByLabel(/^Password/).fill("correct horse battery");
await p.getByRole("button", { name: "Join firm" }).click();
await p.locator("#totp").fill("123456");
await p.getByRole("link", { name: "Team" }).first().waitFor();
await p.getByRole("link", { name: "Team" }).first().click();
await p.getByRole("button", { name: /Invite someone/ }).click();
const offered = await p.locator("fieldset button").allInnerTexts();
ok("Admin is offered staff roles only", offered.length === 3 && !offered.some((t) => /^(Owner|Admin)/.test(t)));
await b.close();
if (failed) process.exit(1); // non-zero exit fails the CI job
