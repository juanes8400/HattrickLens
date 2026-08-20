# 17 — Desarrollo local (backend + frontend a mano, sin Docker)

En la práctica esta cuenta corre sin Docker: backend con `uvicorn` directo
sobre SQLite (`backend/dev.db`), frontend con `vite` directo — no el stack de
`docker compose` que describe el README. Esta guía documenta ese setup real y
los fallos que ya se repitieron más de una vez, para no tener que
redescubrirlos cada sesión.

## Los dos puertos, y por qué NO pueden desalinearse

- **Backend: puerto 8110.** Fijo porque `CHPP_CALLBACK_URL` en `.env`
  (`http://localhost:8110/api/v1/auth/chpp/callback`) está registrado así en
  la app de Hattrick — cambiarlo localmente sin también cambiarlo ahí rompe
  el login.
- **Frontend: puerto 3000**, con el proxy de `/api` en `vite.config.ts`
  apuntando **al mismo puerto 8110**.

El baile OAuth (`GET /auth/chpp/connect` → Hattrick → `GET
/auth/chpp/callback`) guarda el `oauth_token`/secret pendiente en un dict EN
MEMORIA de un solo proceso (`_pending` en `auth_chpp.py` — el propio código
lo marca como deuda técnica: "TODO producción: Redis con TTL, no memoria de
proceso"). Si `/connect` entra por un puerto/proceso y `/callback` entra por
otro, nunca comparten ese estado y Hattrick devuelve
`{"detail":"oauth_token desconocido o ya usado"}` aunque el login en sí haya
sido correcto. **Por eso el proxy de Vite y `CHPP_CALLBACK_URL` deben apuntar
siempre al mismo puerto.** Si algún día se cambia uno, cambiar el otro en el
mismo commit.

## Arrancar todo desde cero (orden y comandos)

```bash
# 1. Verificar que NO hay nada viejo escuchando en 8110 o 3000
powershell -Command "Get-CimInstance Win32_Process -Filter \"name='python.exe'\""
powershell -Command "Get-CimInstance Win32_Process -Filter \"name='node.exe'\""
# Si aparece algo de una sesión anterior, matarlo:
powershell -Command "Stop-Process -Id <PID1>,<PID2> -Force"

# 2. Backend — UN solo proceso, puerto 8110 (coincide con CHPP_CALLBACK_URL)
cd backend
.venv/Scripts/python.exe -u -m uvicorn app.main:app --host 0.0.0.0 --port 8110
# Confirmar en el log: "Application startup complete." y "Uvicorn running on
# http://0.0.0.0:8110" — sin eso, no está listo.

# 3. Frontend — vite normal en 3000
cd frontend
npm run dev
```

`uvicorn` en Windows a veces reporta DOS entradas en
`Get-CimInstance ... python.exe` para un solo servidor real (un lanzador +
el proceso que de verdad escucha, visible en el log como "Started server
process [PID]") — no es por sí solo señal de duplicado. La señal real de
duplicado es que la petición de `/connect` y la de `/callback` devuelvan
resultados inconsistentes (el síntoma de este documento) — en ese caso,
matar TODO lo que use el puerto y arrancar una única instancia limpia.

## Síntomas y su causa real

| Síntoma | Causa real | Arreglo |
|---|---|---|
| El botón "Conectar con Hattrick" no hace nada tras darle "Permitir" | El backend está caído (`ERR_CONNECTION_REFUSED` en la pestaña del callback) | Arrancar el backend (paso 2) |
| `{"detail":"oauth_token desconocido o ya usado"}` | `/connect` y `/callback` cayeron en procesos/puertos distintos (proxy de Vite y `CHPP_CALLBACK_URL` desalineados), o dos procesos backend compitiendo por 8110 | Verificar que ambos apuntan al mismo puerto (sección anterior); matar procesos duplicados; reintentar en una pestaña **nueva** del navegador (ver siguiente fila) |
| Mismo error de `oauth_token`, aun con un solo backend confirmado | La pestaña reutilizó una versión cacheada de la página de autorización de Hattrick, con un token ya quemado de un intento anterior | Abrir una pestaña nueva del navegador para cada intento de conexión, no recargar/reutilizar la misma |
| Tras reiniciar el backend, la SPA queda en blanco o con `SyntaxError: missing ) after argument list` / `ERR_CONNECTION_RESET` en consola | Caché de dependencias de Vite corrupta (`frontend/node_modules/.vite`) tras un reinicio abrupto del dev server | `rm -rf frontend/node_modules/.vite` y reiniciar `npm run dev` |
| La app pide "Conectar con Hattrick" aunque ayer ya estaba conectada, y el backend responde bien | Se perdió la cookie de sesión del perfil del navegador (panel reabierto, perfil nuevo, cookies borradas). Los tokens CHPP siguen en la DB | Navegar a `/api/v1/auth/chpp/dev-session` — NO repetir el OAuth (ver sección dedicada) |
| `vite.config.ts` cambiado pero el navegador sigue pegándole al puerto viejo | Los cambios a `vite.config.ts` NO se recargan en caliente — hace falta matar y volver a arrancar el proceso de `vite` | Matar el proceso `node` de vite y volver a correr `npm run dev` |

## Si SOLO se perdió la cookie de sesión: no repetir el baile OAuth

La sesión vive en una cookie httponly del **perfil del navegador**. Cualquier
cosa que reinicie ese perfil (reabrir el panel de navegador de la herramienta,
un perfil nuevo, borrar cookies) deja al backend y a los datos intactos pero
manda la SPA a la pantalla de "Conectar con Hattrick". **Eso no es un fallo de
OAuth y no requiere volver a autorizar** — los tokens CHPP ya están guardados
y cifrados en `chpp_tokens`.

Para esos casos la app trae `GET /api/v1/auth/chpp/dev-session`
(`auth_chpp.py`, solo con `ENVIRONMENT=local`): instala las cookies de sesión
y redirige a `/connected`, sin tocar Hattrick.

```bash
# Reinstala la sesión local (user_id=1, team_id=1 por defecto) y vuelve a la app
# Basta con navegar a esta URL en el navegador:
#   http://localhost:3000/api/v1/auth/chpp/dev-session
curl -i "http://localhost:8110/api/v1/auth/chpp/dev-session"
```

Repetir el OAuth real solo hace falta cuando cambian los permisos CHPP, cuando
`connectionStatus` viene distinto de `active`, o cuando se conecta una cuenta
nueva. **Nunca pedirle al usuario que vuelva a autorizar sin haber probado
antes `dev-session`**: obliga a teclear usuario y contraseña de Hattrick para
recuperar algo que la base de datos ya tiene.

## Checklist rápido antes de pedirle al usuario que reconecte

0. **¿La app solo muestra la pantalla de conexión, pero el backend y la DB
   están bien?** Entonces es la cookie, no OAuth: usar `dev-session` (sección
   anterior) y parar aquí. Los puntos siguientes solo aplican a un OAuth real.
1. `curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8110/api/v1/auth/chpp/session` → debe dar `401` (no `000`/timeout).
2. Confirmar en `vite.config.ts` que `proxy["/api"].target` apunta al mismo
   puerto que `CHPP_CALLBACK_URL` en `.env`.
3. Un solo proceso backend vivo (ver comandos arriba).
4. Pedir el login en una pestaña nueva, no reutilizada.

Solo después de estos puntos vale la pena pedirle al usuario que intente
conectar — evita hacerlo insistir varias veces por un problema que ya se sabe
diagnosticar de una.
