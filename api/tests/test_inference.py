"""Preprocesamiento: tiene que ser idéntico al del entrenamiento, y rechazar lo que no sirve."""

import io

import pytest
import torch
from PIL import Image

from api.inference import MAX_PIXELS, STORE_SIZE, ImageError, load_image, preprocess
from api.tests.helpers import REPO, make_image, make_pil, to_bytes


@pytest.mark.parametrize("size", [(4000, 3000), (3000, 4000), (640, 480), (100, 80)])
def test_shrink_leaves_short_side_at_320(size):
    img = load_image(make_image(size=size))
    assert min(img.size) == STORE_SIZE
    assert img.mode == "RGB"


def test_preprocess_shape_and_dtype():
    batch = preprocess(load_image(make_image()))
    assert batch.shape == (1, 3, 224, 224)
    assert batch.dtype == torch.float32


def test_exif_rotation_is_applied():
    """Una foto de celular con orientación 6 (girada 90°) se endereza, y es idéntica a la ya enderezada."""
    base = make_pil((640, 480))
    with_exif = load_image(to_bytes(base, "PNG", orientation=6))
    manual = load_image(to_bytes(base.transpose(Image.Transpose.ROTATE_270), "PNG"))
    assert with_exif.size == (320, 427)  # quedó vertical
    assert torch.equal(preprocess(with_exif), preprocess(manual))


def _processed_photos():
    """Una foto reducida de cada clase de Data/processed (están en git: sirven también en GitHub Actions)."""
    photos = [
        sorted((REPO / "Data" / "processed" / label).glob("*.jpg"))[0] for label in ("unripe", "partially_ripe", "ripe")
    ]
    assert all(p.is_file() for p in photos)
    return photos


@pytest.mark.parametrize("path", _processed_photos(), ids=lambda p: p.parent.name)
def test_matches_training_transform_exactly(path):
    """La paridad que importa: lo que ve el modelo en el servidor == lo que vio en el entrenamiento."""
    from dataset import eval_transform  # src/dataset.py, el código del entrenamiento

    trained = eval_transform()(Image.open(path).convert("RGB"))
    served = preprocess(load_image(path.read_bytes()))[0]
    assert torch.equal(trained, served)


@pytest.mark.parametrize("fmt", ["JPEG", "PNG", "WEBP"])
def test_allowed_formats(fmt):
    assert load_image(make_image(fmt)).size[1] == STORE_SIZE


def test_mpo_photos_from_cameras_and_phones_are_accepted():
    """Regresión real: las fotos del dataset y muchas de celular son MPO, no JPEG, y se rechazaban con 415."""
    buf = io.BytesIO()
    make_pil().save(buf, "MPO", save_all=True, append_images=[make_pil()])
    assert Image.open(io.BytesIO(buf.getvalue())).format == "MPO"  # la prueba parte de un MPO de verdad
    assert min(load_image(buf.getvalue()).size) == STORE_SIZE


@pytest.mark.parametrize("fmt", ["GIF", "BMP", "TIFF"])
def test_other_formats_are_415(fmt):
    with pytest.raises(ImageError) as e:
        load_image(make_image(fmt))
    assert e.value.status == 415


@pytest.mark.parametrize("data", [b"esto no es una imagen", b"", b"\xff\xd8\xff garbage"])
def test_garbage_is_400(data):
    with pytest.raises(ImageError) as e:
        load_image(data)
    assert e.value.status == 400


def test_truncated_image_is_400():
    data = make_image(size=(800, 600))
    with pytest.raises(ImageError) as e:
        load_image(data[: len(data) // 2])
    assert e.value.status == 400


@pytest.mark.filterwarnings("ignore::PIL.Image.DecompressionBombWarning")
def test_too_many_pixels_is_413():
    """8000x8000 = 64 millones de píxeles en un PNG que pesa muy poco: debe rechazarse antes de decodificarlo."""
    data = to_bytes(Image.new("L", (8000, 8000)), "PNG")
    assert len(data) < 1_000_000 and 8000 * 8000 > MAX_PIXELS
    with pytest.raises(ImageError) as e:
        load_image(data)
    assert e.value.status == 413


def test_decompression_bomb_is_413():
    """Más del doble del límite: lo frena Pillow antes de que nosotros leamos el tamaño."""
    data = to_bytes(Image.new("L", (12000, 10000)), "PNG")
    with pytest.raises(ImageError) as e:
        load_image(data)
    assert e.value.status == 413


@pytest.mark.parametrize("size", [(4000, 20), (20, 4000)])
def test_extreme_aspect_ratio_is_400(size):
    """Sin esto, reducir una tira de 20x4000 al lado corto 320 pediría una imagen de 64 mil píxeles de alto."""
    with pytest.raises(ImageError) as e:
        load_image(to_bytes(Image.new("RGB", size), "PNG"))
    assert e.value.status == 400


def test_png_with_alpha_and_grayscale_are_converted():
    rgba = to_bytes(Image.new("RGBA", (300, 200), (255, 0, 0, 128)), "PNG")
    gray = to_bytes(Image.new("L", (300, 200), 128), "PNG")
    for data in (rgba, gray):
        assert preprocess(load_image(data)).shape == (1, 3, 224, 224)
