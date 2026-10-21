import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  optimizeDeps: {
    include: [
      "react-hook-form",
      "@hookform/resolvers/zod",
      "zod",
      "react-router-dom",
    ],
  },
  build: {
    // This pinned Rollup build stalls during tree-shaking on this installation.
    // Minification remains enabled; direct per-icon imports keep the graph small.
    // Measured cost: 215.53 kB JS / 67.78 kB gzip versus 212.18 / 67.07 kB.
    rollupOptions: { treeshake: false },
  },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/assets": "http://127.0.0.1:8000",
      "/static/annotated": "http://127.0.0.1:8000",
    },
  },
});
