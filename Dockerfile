# syntax=docker/dockerfile:1
# Imagen multietapa (M11 · 9): la primera etapa instala dependencias en un
# entorno virtual; la final solo copia ese entorno y el código, sin compiladores
# ni cachés de pip. Base fijada a una versión exacta (M11 · 7), nunca `latest`.

# --- Etapa 1: dependencias -----------------------------------------------------
FROM python:3.11.9-slim-bookworm AS constructor
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install -r requirements.txt

# --- Etapa 2: ejecución --------------------------------------------------------
FROM python:3.11.9-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    DATABASE_URL=sqlite:////app/data/app.db

# Usuario sin privilegios: el proceso no corre como root.
RUN useradd --create-home --uid 10001 appuser
WORKDIR /app
COPY --from=constructor /opt/venv /opt/venv
# .dockerignore deja fuera .env, *.db, tests y el entorno virtual local.
COPY --chown=appuser:appuser . .
RUN mkdir -p /app/data && chown appuser:appuser /app /app/data
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import json, sys, urllib.request; r = json.load(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)); sys.exit(0 if r['base_de_datos'] else 1)"

# Aplica las migraciones sobre la base del contenedor y arranca sin --reload,
# escuchando en 0.0.0.0 para que el puerto publicado sea alcanzable desde el host.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn main:app --host 0.0.0.0 --port 8000"]
