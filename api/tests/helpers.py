"""Imágenes de prueba generadas al vuelo y rutas del repo."""

import io
from pathlib import Path

from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[2]


def make_pil(size=(640, 480)):
    """Una 'foto' asimétrica (el óvalo está arriba a la izquierda), para que una rotación se note."""
    img = Image.new("RGB", size, (30, 120, 40))
    w, h = size
    ImageDraw.Draw(img).ellipse([w // 8, h // 8, w // 2, h // 2], fill=(240, 180, 20))
    return img


def to_bytes(img, fmt="JPEG", orientation=None, **kwargs):
    buf = io.BytesIO()
    if orientation:
        exif = Image.Exif()
        exif[0x0112] = orientation  # etiqueta EXIF "Orientation"
        kwargs["exif"] = exif
    img.save(buf, fmt, **kwargs)
    return buf.getvalue()


def make_image(fmt="JPEG", size=(640, 480), orientation=None):
    return to_bytes(make_pil(size), fmt, orientation)


def post_predict(client, data, model="vit_small", filename="foto.jpg", content_type="image/jpeg"):
    return client.post("/predict", data={"file": (io.BytesIO(data), filename, content_type), "model": model})
