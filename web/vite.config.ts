import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    // Aucun module de préchargement inline : la CSP n'autorise que 'self'.
    modulePreload: { polyfill: false },
    assetsInlineLimit: 0,
  },
});
