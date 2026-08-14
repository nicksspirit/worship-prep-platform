import { defineConfig } from "vite";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  // Django owns static assets. Its collectstatic output lives in public/, so Vite
  // must not treat that generated directory as a second source of frontend assets.
  publicDir: false,
  plugins: [tailwindcss()],
});
