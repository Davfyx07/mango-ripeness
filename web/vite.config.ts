import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwind from "@tailwindcss/vite";
const proxy = Object.fromEntries(
  ["health", "models", "predict"].map((path) => [
    "^/" + path + "$",
    "http://127.0.0.1:8000",
  ]),
);
export default defineConfig({
  plugins: [react(), tailwind()],
  server: { port: 5173, strictPort: true, proxy },
  preview: { port: 5173, strictPort: true, proxy },
});
