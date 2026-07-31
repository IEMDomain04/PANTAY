import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [
    react(),
  ],

  server: {
    watch: {
      ignored: [
        "**/backend/**",
        "**/.venv/**",
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
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },

  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});