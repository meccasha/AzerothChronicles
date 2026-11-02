import react from "@vitejs/plugin-react";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": path.resolve(path.dirname(fileURLToPath(import.meta.url)), "src") } },
  test: { environment: "jsdom", include: ["tests/unit/**/*.test.{ts,tsx}"], setupFiles: ["tests/unit/setup.ts"] },
});
