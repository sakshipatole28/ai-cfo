// Live end-to-end test: real browser → console (VITE_API_URL set) → API → database.
// It proves the access model: the Owner creates the firm, grants Admin access, the Admin grants
// staff access, and each role sees only what its role allows.
//
// Start the API and the console first (see "Run it" in README.md), then:
//   E2E_WEB=http://localhost:5173 npm run e2e:live
import { createHmac } from "node:crypto";

import { chromium } from "@playwright/test";

const WEB = process.env.E2E_WEB ?? "http://localhost:5173"; // where the console is served
const PASSWORD = "correct horse battery"; // meets the 12-character rule
const STAMP = Date.now().toString(36); // unique emails so the test can be re-run on the same database

/** Decode a base32 string (the TOTP setup key) into bytes. */
function base32(input) {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  let bits = "";
  for (const ch of input.replace(/=+$/, "")) bits += alphabet.indexOf(ch).toString(2).padStart(5, "0");
  const bytes = [];
  for (let i = 0; i + 8 <= bits.length; i += 8) bytes.push(parseInt(bits.slice(i, i + 8), 2));
  return Buffer.from(bytes);
}

/** The 6-digit code an authenticator app would show now (RFC 6238: HMAC-SHA1, 30-second steps). */
function totp(secret) {
  const counter = Buffer.alloc(8); // 8-byte big-endian time counter
  counter.writeBigUInt64BE(BigInt(Math.floor(Date.now() / 30000)));
  const hash = createHmac("sha1", base32(secret)).update(counter).digest();
  const offset = hash[hash.length - 1] & 0xf; // dynamic truncation
  const value = hash.readUInt32BE(offset) & 0x7fffffff;
  return String(value % 1_000_000).padStart(6, "0");
}

const failures = [];
/** Record a check; the run continues so one failure shows the whole picture. */
function check(name, ok, detail = "") {
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${ok ? "" : ` ${detail}`}`);
  if (!ok) failures.push(name);
}

const browser = await chromium.launch();
const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
page.setDefaultTimeout(15000);

/** Read the authenticator key shown after creating an account and enter the matching code. */
async function finishAuthenticator() {
  const secret = (await page.locator("code").first().innerText()).trim(); // the setup key
  await page.locator("#totp").fill(totp(secret)); // typing the sixth digit submits
  await page.getByText(/Welcome,/).first().waitFor();
}

/** Open the account menu and sign out. */
async function signOut() {
  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await page.getByRole("button", { name: /Create a firm account/ }).waitFor();
}

/** Go to the Team page through the sidebar (the app keeps its state in memory). */
async function openTeam() {
  await page.getByRole("link", { name: "Team" }).first().click();
  await page.getByText("What each role can do").waitFor();
}

/** Owner or Admin invites someone; returns the one-time code. */
async function invite(name, email, role) {
  await page.getByRole("button", { name: /Invite someone/ }).click();
  await page.locator("#inv-name").fill(name);
  await page.locator("#inv-email").fill(email);
  await page.getByRole("button", { name: new RegExp(`^${role}`) }).click(); // the role card
  await page.getByRole("button", { name: "Create invite" }).click();
  const code = (await page.locator("code").first().innerText()).trim();
  await page.getByRole("button", { name: "Done" }).click();
  return code;
}

/** A new employee joins with their invite code and sets up their authenticator. */
async function join(code, name, email) {
  await page.getByRole("button", { name: /Join with an invite code/ }).click();
  await page.getByLabel("Invite code").fill(code);
  await page.getByLabel("Your full name").fill(name);
  await page.getByLabel(/Work email/).fill(email);
  await page.getByLabel(/^Password/).fill(PASSWORD);
  await page.getByRole("button", { name: "Join firm" }).click();
  await finishAuthenticator();
}

const owner = `owner-${STAMP}@e2e.example`;
const admin = `admin-${STAMP}@e2e.example`;
const adviser = `adviser-${STAMP}@e2e.example`;

// 1. The Owner creates the firm.
await page.goto(`${WEB}/signin`);
await page.getByRole("button", { name: /Create a firm account/ }).click();
await page.getByLabel("Firm name").fill(`E2E Wealth ${STAMP}`);
await page.getByLabel(/SEBI registration/).fill("INA000099999");
await page.getByLabel("Your full name").fill("Olive Owner");
await page.getByLabel(/Work email/).fill(owner);
await page.getByLabel(/^Password/).fill(PASSWORD);
await page.getByRole("button", { name: "Create firm" }).click();
await finishAuthenticator();
check("Owner created the firm and is signed in", await page.getByText(`E2E Wealth ${STAMP}`).first().isVisible());

// 2. A refresh keeps the session (token in sessionStorage, restored from the API).
await page.reload();
await page.getByRole("link", { name: "Team" }).first().waitFor();
check("session survives a page refresh", true);

// 3. The Owner grants Admin access.
await openTeam();
const adminCode = await invite("Asha Admin", admin, "Admin");
check("Owner can invite an Admin (invite code issued)", /^[0-9A-F]{10}$/.test(adminCode), adminCode);
await signOut();

// 4. The Admin joins with that code, and can grant staff roles only.
await join(adminCode, "Asha Admin", admin);
await openTeam();
check("Admin sees the Invite button", await page.getByRole("button", { name: /Invite someone/ }).isVisible());
check("Owner's role is read-only for an Admin", (await page.locator("select").count()) === 0);
await page.getByRole("button", { name: /Invite someone/ }).click();
const offered = await page.locator("fieldset button").allInnerTexts();
check("Admin is offered Adviser/Analyst/Compliance only", offered.length === 3 && !offered.some((t) => /^(Owner|Admin)/.test(t)), JSON.stringify(offered));
await page.keyboard.press("Escape"); // close the sheet before inviting again
const code2 = await invite("Ravi Adviser", adviser, "Adviser");
check("Admin can invite an Adviser", /^[0-9A-F]{10}$/.test(code2), code2);
await signOut();

// 5. The Adviser joins; they can read the team page but not manage it.
await join(code2, "Ravi Adviser", adviser);
await openTeam();
check("Adviser has no Invite button", (await page.getByRole("button", { name: /Invite someone/ }).count()) === 0);
check("Adviser sees the read-only notice", await page.getByText("Only Owners and Admins can change the team").isVisible());

// 6. An invite code works only once.
await signOut();
await page.getByRole("button", { name: /Join with an invite code/ }).click();
await page.getByLabel("Invite code").fill(code2);
await page.getByLabel("Your full name").fill("Someone Else");
await page.getByLabel(/Work email/).fill(`late-${STAMP}@e2e.example`);
await page.getByLabel(/^Password/).fill(PASSWORD);
await page.getByRole("button", { name: "Join firm" }).click();
// The refusal arrives as a toast a moment after the click, so wait for it instead of reading it at once.
const refused = await page.getByText(/not valid/i).first().waitFor({ timeout: 5000 }).then(() => true, () => false);
check("a used invite code is refused", refused);

await browser.close();
if (failures.length) {
  console.error(`\n${failures.length} check(s) failed: ${failures.join("; ")}`);
  process.exit(1);
}
console.log("\nAll live end-to-end checks passed.");
