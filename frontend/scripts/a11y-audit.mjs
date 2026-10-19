// Accessibility audit (WCAG 2 A/AA, incl. colour contrast) of every main page in light and dark.
// Usage: npm run build:preview && npm run audit:a11y
import AxeBuilder from "@axe-core/playwright";
import { chromium } from "@playwright/test";

const file = "file://" + process.cwd() + "/dist-preview/index.html";
const pages = ["Today", "Review inbox", "Clients", "Agents", "Ask the rulebook", "Client access", "Team", "Settings", "Audit trail"];
const browser = await chromium.launch();
const failures = [];
for (const dark of [false, true]) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: dark ? "dark" : "light" });
  const p = await ctx.newPage();
  await p.goto(file);
  await p.waitForTimeout(300);
  const check = async (name) => {
    await p.evaluate(() => document.querySelectorAll("[data-sonner-toast]").forEach((t) => t.remove()));
    const r = await new AxeBuilder({ page: p }).withTags(["wcag2a", "wcag2aa"]).analyze();
    for (const v of r.violations) failures.push(`${dark ? "dark" : "light"} ${name}: ${v.id} (${v.nodes.length})`);
  };
  await check("Sign in");
  await p.getByRole("button", { name: /Priya Anand/ }).first().click();
  await p.getByRole("button", { name: "Continue" }).click();
  await p.locator("#totp").fill("123456");
  await p.waitForTimeout(1400);
  for (const label of pages) {
    await p.getByRole("link", { name: label }).first().click();
    await p.waitForTimeout(400);
    await check(label);
  }
  await ctx.close();
}
await browser.close();
if (failures.length) {
  console.error(failures.join("\n"));
  process.exit(1);
}
console.log(`axe: 0 violations on ${pages.length + 1} pages in light and dark`);
