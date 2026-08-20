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

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY backend/pyproject.toml backend/uv.lock* ./
RUN uv sync --frozen --no-dev || uv sync --no-dev

COPY backend/ ./
COPY --from=frontend /app/dist ./static

ENV PATH="/code/.venv/bin:$PATH"
# El hosting decide el puerto; 8000 es solo el valor por defecto.
ENV PORT=8000
EXPOSE 8000

# Migraciones antes de arrancar: la base de un servicio gratuito empieza vacía
# y nadie va a entrar a ejecutarlas a mano.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
