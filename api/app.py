"""API Flask del portal de maduración del mango. El contrato con la interfaz está en api/CONTRATO.md.

Variables de entorno (todas opcionales):
    MANGO_MODELS_DIR    carpeta con los .pt   (por defecto api/models)
    MANGO_CORS_ORIGINS  orígenes permitidos, separados por coma (por defecto, los de desarrollo local)
    MANGO_PRELOAD       "1" carga los 5 modelos al arrancar con gunicorn (por defecto "1"; ver wsgi.py)
    MANGO_MAX_UPLOAD_MB límite de tamaño de la foto en MB (por defecto 25; en Lambda, 5)
"""

import os
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from werkzeug.exceptions import HTTPException, MethodNotAllowed

from .inference import CATALOG, ImageError, Registry, load_image, preprocess

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ORIGINS = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000"
MAX_UPLOAD_MB = 25  # varias fotos de cámara pasan de 10 MB; los píxeles se limitan aparte


def find_web_dir():
    """La interfaz compilada (web/dist) o, si no hay, web/ con su index.html. None si no hay ninguna."""
    for candidate in (ROOT / "web" / "dist", ROOT / "web"):
        if (candidate / "index.html").is_file():
            return candidate
    return None


def create_app(models_dir=None, web_dir="auto", cors_origins=None, max_upload_mb=None):
    """Crea la aplicación. Los parámetros existen para poder probarla con otras carpetas y límites."""
    if max_upload_mb is None:
        max_upload_mb = int(os.environ.get("MANGO_MAX_UPLOAD_MB", MAX_UPLOAD_MB))
    app = Flask(__name__)
    app.json.ensure_ascii = False  # los mensajes en español salen legibles
    app.json.sort_keys = False  # las probabilidades salen en orden de maduración, no alfabético
    app.config["MAX_CONTENT_LENGTH"] = max_upload_mb * 1024 * 1024

    registry = Registry(models_dir or os.environ.get("MANGO_MODELS_DIR") or ROOT / "api" / "models")
    app.extensions["registry"] = registry

    if cors_origins is None:
        cors_origins = os.environ.get("MANGO_CORS_ORIGINS", DEFAULT_ORIGINS).split(",")
    CORS(app, origins=[o.strip() for o in cors_origins if o.strip()], methods=["GET", "POST"])

    def error(status, message):
        return jsonify({"detail": message}), status

    @app.errorhandler(HTTPException)
    def http_error(e):
        messages = {
            404: "Ruta no encontrada",
            405: "Método no permitido",
            413: f"La imagen pesa más de {max_upload_mb} MB",
        }
        return error(e.code, messages.get(e.code, e.description))

    @app.errorhandler(Exception)
    def unexpected_error(e):
        app.logger.exception("Error inesperado")
        return error(500, "Error interno del servidor")  # sin detalles: no se filtra nada del servidor

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "models_available": len(registry.available())})

    @app.get("/models")
    def models():
        return jsonify(
            [
                {"id": mid, **{k: CATALOG[mid][k] for k in ("nombre", "familia", "accuracy_test")}}
                for mid in registry.options()
            ]
        )

    @app.post("/predict")
    def predict():
        file = request.files.get("file")
        model_id = request.form.get("model")
        if file is None or not model_id:
            return error(422, "Faltan los campos 'file' (la imagen) y 'model' (el id del modelo)")
        available = registry.options()
        if not available:
            return error(503, "No hay modelos cargados en el servidor")
        if model_id not in available:
            return error(404, f"El modelo '{model_id}' no existe")
        data = file.read()
        if not data:
            return error(400, "El archivo está vacío")
        try:
            batch = preprocess(load_image(data))
        except ImageError as e:
            return error(e.status, str(e))
        result = registry.predict(model_id, batch)
        app.logger.info("predict model=%s label=%s ms=%s", model_id, result["label"], result["inference_ms"])
        response = jsonify(result)
        response.headers["Cache-Control"] = "no-store"
        return response

    if web_dir == "auto":
        web_dir = find_web_dir()
    if web_dir:  # sirve la interfaz desde el mismo servidor: un solo enlace y sin problemas de CORS

        @app.get("/")
        def index():
            return send_from_directory(web_dir, "index.html")

        @app.get("/<path:path>")
        def static_file(path):
            if path == "predict":  # la ruta existe pero solo acepta POST: sin esto saldría un 404 engañoso
                raise MethodNotAllowed(valid_methods=["POST"])
            return send_from_directory(web_dir, path)  # rechaza rutas que salgan de la carpeta

    return app
