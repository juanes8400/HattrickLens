# Publicar HT Lens

Escrito el 2026-08-19, al preparar la primera versión abierta a otros managers.

## Lo primero: la app NO estaba lista para varios usuarios

Antes de tocar nada de infraestructura, una auditoría de las rutas encontró el
agujero que lo bloqueaba todo:

> **32 de las 53 rutas con `{team_id}` no comprobaban nada**, y la mayoría ni
> siquiera pedía sesión.

Con un solo usuario no se nota, porque siempre es el equipo 1. Con dos, cambiar
el número de la URL enseñaba la plantilla, la economía, las alertas y las
fichas de rival del otro.

Está cerrado así:

- `require_team_owner` (en `app/api/deps.py`) exige sesión y comprueba que el
  equipo de la URL pertenece a quien pregunta. Devuelve 401 sin sesión, 403 con
  el equipo de otro y 404 si el equipo no existe.
- Declarada como dependencia **en las 45 rutas** con `{team_id}`.
- `tests/test_team_isolation.py` recorre la aplicación entera y falla si
  aparece una ruta nueva sin ella. Ese test es la garantía real; el resto de la
  suite desactiva la comprobación para no repetir el mismo login en cada test
  de forma o de cálculo.

Otras dos cosas del mismo repaso:

- Las cookies de sesión llevan `secure` fuera de local, así que no viajan por
  http.
- `/auth/chpp/dev-session` (que instala una sesión sin credencial) ya estaba
  bloqueado fuera de `ENVIRONMENT=local`. Confirmado, no tocado.

## Qué se despliega

Una sola imagen con la API y la pantalla dentro (`Dockerfile` en la raíz):

1. Construye el frontend con Node.
2. Lo copia a `backend/static`, desde donde FastAPI lo sirve.
3. Arranca aplicando las migraciones (`alembic upgrade head`) y después
   `uvicorn`.

Un solo proceso y un solo puerto, que es lo que cabe en un plan gratuito. Y de
paso el navegador ve el mismo origen: la cookie de sesión viaja sin CORS ni
dominios cruzados. El frontend ya apunta a `/api/v1` del mismo origen, así que
no hay ninguna URL que configurar.

## Variables de entorno

Están en `.env.example`, con el comando para generar cada clave. Las tres que
no pueden faltar:

| Variable | Para qué |
|---|---|
| `SECRET_KEY` | firma las cookies de sesión |
| `TOKEN_ENCRYPTION_KEY` | cifra los tokens CHPP guardados (Fernet) |
| `DATABASE_URL` | Postgres del hosting (`postgresql+asyncpg://…`) |

Si alguna se filtra, se regenera: las sesiones y los tokens guardados dejan de
valer, que es exactamente lo que se quiere.

`REDIS_URL` dejó de ser obligatoria: no se usa en el código, la caché vive en
memoria del proceso.

## CHPP: el paso que no depende de nosotros

Hattrick tiene que aprobar la aplicación antes de que otros managers puedan
conectarse. Sin eso, el resto no sirve.

1. Registrar la app en <https://chpp.hattrick.org>.
2. La **URL de retorno** debe ser exactamente
   `https://tu-dominio/api/v1/auth/chpp/callback`. Si no coincide carácter a
   carácter, Hattrick rechaza el intercambio de tokens.
3. Poner un `CHPP_USER_AGENT` con el nombre real y una forma de contacto: es lo
   que miran si la app se comporta mal.
4. Contar cuántas llamadas hace: una sincronización normal son unas 30, y la
   ficha de un rival unas 20 la primera vez (después van por la caché de cinco
   minutos). Con varios usuarios sincronizando a la vez eso se multiplica, y es
   el primer sitio donde CHPP puede cortar el grifo.

## Dónde alojarlo gratis

Cualquier sitio que corra un contenedor y ofrezca Postgres. Al día de escribir
esto, las opciones habituales son Render, Fly.io y Railway, todas con planes
gratuitos que cambian cada pocos meses, así que conviene mirar sus condiciones
antes que fiarse de esta lista.

Dos cosas a tener en cuenta con cualquiera de ellos:

- **El servicio gratuito se duerme.** La primera visita tras un rato tarda
  bastante en responder. No rompe nada, pero se nota.
- **La base de datos gratuita no tiene copias de seguridad**, y en varios
  proveedores caduca a los treinta o noventa días. Todo lo que guarda HT Lens
  se puede reconstruir sincronizando otra vez, salvo el histórico de snapshots,
  que es justo lo que da valor a las gráficas de evolución. Merece la pena
  exportar la base de vez en cuando.

## Comprobaciones después de desplegar

1. `GET /health` responde `{"status": "ok"}`.
2. Entrar sin sesión a `/api/v1/teams/1/overview` responde **401**.
3. Conectar una cuenta de Hattrick y comprobar que redirige y sincroniza.
4. Con esa sesión, pedir el equipo de otro id responde **403**.
5. `/api/v1/docs` enseña la API; decidir si se quiere pública o no.

## Lo que queda pendiente

- **Un club, un dueño.** Si dos personas conectan el mismo club, la última se
  queda con él (`team.owner_user_id` se reasigna). Para clubes con más de un
  manager haría falta una tabla `user_teams`, que ya está prevista en el modelo
  pero no construida.
- **Un proceso, un contador.** El límite de peticiones vive en memoria: con dos
  contenedores el tope real sería el doble.
- **La caché de CHPP ya no se comparte entre usuarios**, así que dos managers
  mirando al mismo rival gastan el doble de llamadas que antes. Es el precio de
  no filtrar alineaciones.

## Lo que se añadió para multiusuario (2026-08-19, segunda tanda)

### La caché de CHPP no distinguía usuarios

La ficha de rival cachea sus consultas cinco minutos para que mover un toggle
no cueste veinte llamadas. La clave era `(fichero, versión, parámetros)`, sin
el usuario dentro.

Para datos públicos de un rival eso da igual. El problema es `matchorders`, que
devuelve **la alineación que tú enviaste** y solo la ve su dueño: con dos
managers que se enfrentan, el segundo en abrir la ficha recibía el once del
primero antes del partido. Ahora el usuario forma parte de la clave.

El precio es cachear por separado lo que sí es público. Compartirlo ahorraría
llamadas, pero exigiría clasificar fichero por fichero cuál depende del token,
y equivocarse una sola vez vuelve a abrir la fuga.

### Límite de peticiones por usuario

La cuota de CHPP es de la aplicación entera: uno sincronizando en bucle deja
sin acceso a todos a la vez, y basta con una pestaña que recargue sola.

`app/api/rate_limit.py` limita lo que gasta llamadas a Hattrick (sincronizar,
fichas de rival, comparativa de liga), no lo que solo lee la base. Dos cubos
separados por usuario: quedarte sin sincronizaciones no te deja sin poder mirar
un rival. Seis sincronizaciones y treinta consultas de rival por hora.

El contador vive en memoria del proceso, que es suficiente con un solo
contenedor. Con varios, cada uno llevaría su cuenta y el límite real sería la
suma; el sitio para arreglarlo es ese módulo.

### Borrar la cuenta

`DELETE /api/v1/auth/chpp/account` borra al usuario, sus equipos y todo lo
sincronizado. Va por equipo recorriendo lo que cuelga de `teams.id`, para que
una tabla nueva que se olvide de añadirse ahí deje huérfanos visibles en vez de
datos personales escondidos.

Hay un test que comprueba lo que de verdad importa: que borrando la cuenta de
uno **no se toque la del otro**.
