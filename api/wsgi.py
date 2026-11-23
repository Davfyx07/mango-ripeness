"""Punto de entrada para producción:  gunicorn api.wsgi:app  (desde la raíz del repo)."""

import os

from .app import create_app

app = create_app()
if os.environ.get("MANGO_PRELOAD", "1") == "1":
    app.extensions["registry"].preload()  # los 5 modelos listos antes de recibir la primera petición
