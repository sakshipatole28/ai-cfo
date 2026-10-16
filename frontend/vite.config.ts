import { fileURLToPath } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { viteSingleFile } from "vite-plugin-singlefile";

// `--mode preview` builds a single self-contained HTML file for sharing a live demo.
export default defineConfig(({ mode }) => ({
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  plugins: [react(), tailwindcss(), ...(mode === "preview" ? [viteSingleFile()] : [])],
  build:
    mode === "preview"
      ? { outDir: "dist-preview", assetsInlineLimit: 100_000_000, chunkSizeWarningLimit: 5000 }
      : { chunkSizeWarningLimit: 1200 },
}));
