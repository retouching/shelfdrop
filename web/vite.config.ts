import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // pnpm dev : l'API tourne à côté (uvicorn, port 8000).
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
  build: {
    // Aucun module de préchargement inline : la CSP n'autorise que 'self'.
    modulePreload: { polyfill: false },
    assetsInlineLimit: 0,
  },
});
