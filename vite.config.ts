import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig(({ mode }) => ({
  plugins: [react()],

  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    allowedHosts: mode === "development" ? [".trycloudflare.com"] : [],
    watch: {
      ignored: [
        "**/backend/**",
        "**/.venv/**",
        "**/data/**",
        "**/database/**",
        "**/documents/**",
        "**/embeddings/**",
        "**/models/**",
        "**/rag/**",
        "**/dist/**",
      ],
    },
    proxy: {
      "/api": {
        target: process.env.VITE_API_PROXY_TARGET ?? "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },

  preview: {
    host: "0.0.0.0",
    port: 4173,
  },

  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "./src"),
    },
  },

  build: {
    target: "es2022",
    sourcemap: mode !== "production",
    cssCodeSplit: true,
    reportCompressedSize: false,
    chunkSizeWarningLimit: 700,
  },

  optimizeDeps: {
    include: ["react", "react-dom"],
  },
}));
