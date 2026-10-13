# Dockerfile para Finart S.A.S. · Dashboard ARDP Falabella
FROM python:3.13-slim AS base

# Configurar variables de entorno de Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8501

WORKDIR /app

# Instalar dependencias del sistema mínimas
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias de Python fijadas
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código del proyecto
COPY . .

# Crear usuario no privilegiado por seguridad
RUN addgroup --system finartgroup && adduser --system --ingroup finartgroup finartuser \
    && mkdir -p /app/datos /app/logs /app/backups \
    && chown -R finartuser:finartgroup /app

USER finartuser

EXPOSE 8501

# Healthcheck interno de Streamlit
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
