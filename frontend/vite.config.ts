import { execSync } from "node:child_process";
import { defineConfig, loadEnv, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import paquete from "./package.json" with { type: "json" };

/** El commit del que saliÃ³ este build.
 *
 *  La versiÃ³n de `package.json` dice quÃ© release es; esto dice quÃ© CÃ“DIGO
 *  hay delante, que es la pregunta que de verdad se hace uno mirando la
 *  pantalla: Â«Â¿esto ya tiene el arreglo de ayer?Â».
 *
 *  Si git no estÃ¡ --el contenedor de despliegue construye desde una copia sin
 *  historial-- se queda vacÃ­o y la pantalla enseÃ±a sÃ³lo la versiÃ³n. Fallar la
 *  compilaciÃ³n por no poder adornar una etiqueta serÃ­a absurdo.
 */
function commit(): string {
  try {
    return execSync("git rev-parse --short HEAD", {
      stdio: ["ignore", "pipe", "ignore"],
    })
      .toString()
      .trim();
  } catch {
    return "";
  }
}

/** Escribe `ads.txt` en la raíz del sitio, con el editor de AdSense.
 *
 *  POR QUÉ GENERADO Y NO UN FICHERO EN `public/`. `ads.txt` sólo vale si
 *  lleva el identificador REAL: uno de ejemplo, o un hueco a medio rellenar,
 *  hace que Google lo lea como «nadie está autorizado a vender este
 *  inventario» y deje de servir anuncios, sin romper nada visible. Teniéndolo
 *  en el entorno hay una sola fuente de verdad, la misma que usa el código.
 *
 *  SIN EDITOR CONFIGURADO NO SE ESCRIBE NADA, y eso es lo correcto: un sitio
 *  sin publicidad no debe afirmar que autoriza a vender la suya.
 *
 *  OJO CON EL PREFIJO: en el código el cliente va como `ca-pub-…` y en
 *  `ads.txt` va como `pub-…`. Es la fuente de error más tonta de todo esto.
 */
function adsTxt(cliente: string): Plugin {
  return {
    name: "htlens-ads-txt",
    apply: "build",
    generateBundle() {
      if (!/^ca-pub-\d{16}$/.test(cliente)) return;
      this.emitFile({
        type: "asset",
        fileName: "ads.txt",
        source:
          "google.com, " +
          cliente.replace(/^ca-/, "") +
          ", DIRECT, f08c47fec0942fa0\n",
      });
    },
  };
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "VITE_");
  return {
    plugins: [react(), adsTxt(env.VITE_ADSENSE_CLIENT ?? "")],
    define: {
      __VERSION__: JSON.stringify(paquete.version),
      __COMMIT__: JSON.stringify(commit()),
    },
    server: {
      port: 3000,
      // El backend expone el callback de OAuth de Hattrick en el puerto 8110
      // (CHPP_CALLBACK_URL en .env, registrado asÃ­ en la app de Hattrick â€” no
      // se puede cambiar sin mÃ¡s). El proxy de la SPA debe apuntar al MISMO
      // puerto: el estado pendiente del baile OAuth vive en memoria de un
      // solo proceso (`_pending` en auth_chpp.py), asÃ­ que si /connect entra
      // por un puerto y /callback por otro, nunca comparten el token.
      proxy: {
        "/api": { target: "http://localhost:8110", changeOrigin: true },
      },
    },
    // Las entradas de la librerÃ­a de grÃ¡ficas, declaradas a mano.
    //
    // Se piden desde un trozo DIFERIDO (`charts/Chart.tsx`), asÃ­ que el
    // pre-empaquetador no las ve al arrancar: las descubre cuando el navegador
    // abre la primera grÃ¡fica, y re-optimizar con peticiones en vuelo tumbaba
    // el servidor de desarrollo con Â«Cannot read properties of undefined
    // (reading 'imports')Â». DeclarÃ¡ndolas se preparan al arrancar, una vez
    // (2026-09-20).
    optimizeDeps: {
      include: [
        "echarts/core",
        "echarts/charts",
        "echarts/components",
        "echarts/renderers",
      ],
    },
    build: { outDir: "dist", sourcemap: true },
    test: {
      // Los tests viven junto al cÃ³digo que prueban, dentro de src/.
      include: ["src/**/*.{test,spec}.{ts,tsx}"],
      // `.pytest_cache` se colÃ³ aquÃ­ como directorio suelto y sin permisos de
      // lectura; vitest escanea la raÃ­z por defecto y se cae con EPERM antes de
      // llegar a correr nada. Acotar el escaneo lo evita sin tocar el disco.
      exclude: ["node_modules/**", "dist/**", ".pytest_cache/**"],
    },
  };
});
