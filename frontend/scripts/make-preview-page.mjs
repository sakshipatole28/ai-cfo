// Turns the single-file Vite build into a page body for sharing as a hosted preview.
import { readFileSync, writeFileSync } from "node:fs";

const html = readFileSync("dist-preview/index.html", "utf8");
const head = html.match(/<head>([\s\S]*?)<\/head>/)?.[1] ?? "";
const body = html.match(/<body>([\s\S]*?)<\/body>/)?.[1] ?? "";
const styles = [...head.matchAll(/<style[\s\S]*?<\/style>/g)].map((m) => m[0]).join("\n");
const scripts = [...head.matchAll(/<script[\s\S]*?<\/script>/g)].map((m) => m[0]).join("\n");
const page = [
  "<title>AI CFO Console</title>",
  '<meta name="claude:viewport-fit-sides" content="cover">',
  styles,
  body.trim(),
  scripts,
].join("\n");
writeFileSync("dist-preview/ai-cfo-console.html", page);
console.log(`dist-preview/ai-cfo-console.html ${(page.length / 1024).toFixed(0)} KB`);
