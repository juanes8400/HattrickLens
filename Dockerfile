# Una sola imagen con la API y la pantalla dentro.
#
# Es lo que cabe en el plan gratuito de casi cualquier hosting (un servicio, un
# puerto) y de paso el navegador ve el mismo origen, así que la cookie de
# sesión viaja sin CORS ni dominios cruzados.

# ── 1. Construir el frontend ────────────────────────────────────────────────
FROM node:22-slim AS frontend
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
# Las llamadas van a /api del mismo origen, así que no hace falta ninguna URL
# de API en tiempo de construcción.
RUN npm run build

# ── 2. La aplicación ────────────────────────────────────────────────────────
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /code

# `uv` con la versión escrita: con `:latest` cada despliegue podía traer un
# instalador distinto del que pasó las pruebas.
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /usr/local/bin/uv
# El Python es el de la imagen. Si un día no casa con `.python-version`, que la
# construcción falle en vez de bajarse otro por su cuenta.
ENV UV_PYTHON_DOWNLOADS=never
COPY backend/pyproject.toml backend/uv.lock backend/.python-version ./
# `--locked` instala exactamente lo que dice `uv.lock` y además se niega a
# seguir si el lock ya no corresponde a `pyproject.toml`. Aquí había un
# `|| uv sync --no-dev` que, sin lock, resolvía versiones nuevas en cada
# despliegue sin avisar: producción corría con paquetes que nadie había probado.
RUN uv sync --locked --no-dev

COPY backend/ ./
COPY --from=frontend /app/dist ./static

ENV PATH="/code/.venv/bin:$PATH"
# El hosting decide el puerto; 8000 es solo el valor por defecto.
ENV PORT=8000
EXPOSE 8000

# Migraciones antes de arrancar: la base de un servicio gratuito empieza vacía
# y nadie va a entrar a ejecutarlas a mano.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
