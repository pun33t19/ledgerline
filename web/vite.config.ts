/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The built app is served by the Python API (`ledgerline ui`), so it is written into the package.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    outDir: "../src/ledgerline/api/static",
    emptyOutDir: true,
    sourcemap: false,
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: {
      // `ledgerline ui --dev --no-browser` runs the API on :8765.
      "/api": { target: "http://127.0.0.1:8765", changeOrigin: true, ws: true },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    css: false,
  },
});
