import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    outDir: "../dist/webview",
    emptyOutDir: true,
    rollupOptions: {
      input: path.resolve(__dirname, "index.html"),
      output: {
        entryFileNames: "index.js",
        chunkFileNames: "[name].js",
        assetFileNames: "[name][extname]",
      },
    },
  },
  resolve: {
    alias: [
      // Override the API client — routes through postMessage bridge instead of fetch
      { find: "@/lib/api", replacement: path.resolve(__dirname, "src/lib/api.ts") },
      { find: "@/lib/queryClient", replacement: path.resolve(__dirname, "src/lib/queryClient.ts") },
      // Override deployment mode — reads dev mode from extension host via postMessage
      { find: "@/hooks/useDeploymentMode", replacement: path.resolve(__dirname, "src/lib/useDeploymentMode.ts") },
      // Stub react-router-dom for webview (no URL routing)
      { find: "react-router-dom", replacement: path.resolve(__dirname, "src/lib/routerStub.ts") },
      // Everything else imports directly from the frontend source
      { find: /^@\//, replacement: path.resolve(__dirname, "../../frontend/src") + "/" },
    ],
    // Force shared packages to resolve from webview-ui's node_modules to prevent
    // duplicate module instances when frontend components import them.
    dedupe: [
      "react",
      "react-dom",
      "@tanstack/react-query",
      "zustand",
      "@xyflow/react",
    ],
  },
});
