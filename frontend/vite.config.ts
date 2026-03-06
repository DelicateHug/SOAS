import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
      // Alias y-prosemirror → @tiptap/y-tiptap so the Collaboration and
      // CollaborationCursor extensions share the same PluginKey instances.
      "y-prosemirror": path.resolve(__dirname, "node_modules/@tiptap/y-tiptap"),
    },
    dedupe: ["yjs", "@tiptap/y-tiptap", "prosemirror-state", "prosemirror-view", "prosemirror-model"],
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          "vendor-react": ["react", "react-dom", "react-router-dom"],
          "vendor-graph": ["@xyflow/react"],
          "vendor-recharts": ["recharts"],
          "vendor-tanstack": ["@tanstack/react-query"],
          "vendor-zustand": ["zustand"],
        },
      },
    },
  },
  server: {
    port: 5173,
    watch: {
      usePolling: true,
      interval: 1000,
    },
    proxy: {
      "/api": {
        target: process.env.VITE_API_URL || "http://localhost:8000",
        changeOrigin: true,
        ws: true,
      },
    },
  },
});
