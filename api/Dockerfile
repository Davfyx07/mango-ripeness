# Imagen del backend (CPU). Se construye desde la RAÍZ del repo:
#   docker build -f api/Dockerfile -t mango-api .
#   docker run -p 8000:8000 mango-api            (los .pt tienen que estar en api/models/ al construir)
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000 \
    MANGO_MODELS_DIR=/app/api/models \
    AWS_LWA_PORT=8000 \
    AWS_LWA_READINESS_CHECK_PATH=/health

WORKDIR /app

# Primero las librerías, para que Docker las reutilice si solo cambia el código
COPY api/requirements.txt api/requirements.txt
RUN pip install torch==2.14.1 torchvision==0.29.1 --index-url https://download.pytorch.org/whl/cpu \
    && pip install -r api/requirements.txt

COPY api api

# Lambda Web Adapter: deja que Lambda hable con este servidor web. Fuera de Lambda no hace nada.
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:1.0.0 /lambda-adapter /opt/extensions/lambda-adapter

# No corre como administrador dentro del contenedor
RUN useradd --create-home app && chown -R app /app
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://localhost:%s/health' % os.environ['PORT'])"]

# 1 proceso y 2 hilos: los 5 modelos ocupan unos 2 GB de RAM y no se duplican por proceso.
# $PORT lo pone Cloud Run (y otras plataformas); en local es 8000.
CMD gunicorn api.wsgi:app --bind 0.0.0.0:$PORT --workers 1 --threads 2 --timeout 120
