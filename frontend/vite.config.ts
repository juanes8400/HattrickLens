import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    // El backend expone el callback de OAuth de Hattrick en el puerto 8110
    // (CHPP_CALLBACK_URL en .env, registrado así en la app de Hattrick — no
    // se puede cambiar sin más). El proxy de la SPA debe apuntar al MISMO
    // puerto: el estado pendiente del baile OAuth vive en memoria de un
    // solo proceso (`_pending` en auth_chpp.py), así que si /connect entra
    // por un puerto y /callback por otro, nunca comparten el token.
    proxy: { "/api": { target: "http://localhost:8110", changeOrigin: true } },
  },
  build: { outDir: "dist", sourcemap: true },
  test: {
    // Los tests viven junto al código que prueban, dentro de src/.
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    // `.pytest_cache` se coló aquí como directorio suelto y sin permisos de
    // lectura; vitest escanea la raíz por defecto y se cae con EPERM antes de
    // llegar a correr nada. Acotar el escaneo lo evita sin tocar el disco.
    exclude: ["node_modules/**", "dist/**", ".pytest_cache/**"],
  },
});
