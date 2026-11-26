"""Preprocesamiento, carga de modelos y predicción. No depende de Flask: se puede probar sola.

El preprocesamiento replica el del entrenamiento (src/prepare_data.py y src/dataset.py): una foto del
usuario pasa por los mismos pasos que pasó cada foto de entrenamiento. Si alguno de estos valores o pasos
cambia, el modelo falla en silencio. api/tests/test_inference.py comprueba que siguen iguales.
"""

import io
import threading
import time
from pathlib import Path

import timm
import torch
from PIL import Image, ImageOps, UnidentifiedImageError
from torchvision.transforms import v2 as T

CLASSES = ["unripe", "partially_ripe", "ripe"]  # mismo orden que src/config.py: la posición es la etiqueta
STORE_SIZE = 320  # lado corto de la foto después de reducirla
IMG_SIZE = 224  # tamaño que entra al modelo
MEAN = [0.485, 0.456, 0.406]  # media y desviación de ImageNet, como en el entrenamiento
STD = [0.229, 0.224, 0.225]

# El formato se detecta por el contenido, no por el nombre. MPO es un JPEG con varias imágenes (muchos celulares
# y cámaras lo usan, por ejemplo con modo retrato): se abre como JPEG y se usa la primera imagen.
ALLOWED_FORMATS = {"JPEG", "MPO", "PNG", "WEBP"}
MAX_PIXELS = 50_000_000  # una foto de celular de 12 MP tiene 12 millones: esto frena bombas de descompresión
MAX_ASPECT = 8  # una tira de 1x50000 px reducida al lado corto 320 ocuparía gigas de memoria
Image.MAX_IMAGE_PIXELS = MAX_PIXELS  # Pillow avisa al pasarse y falla al duplicarlo

# id que ve la interfaz -> modelo. `arch` es el nombre en timm; el archivo de pesos se llama igual.
# accuracy_test sale de results/v0.2_dos_pc/ensemble_results.csv (114 fotos de estudio; lo comprueba un test).
MODELS = {
    "resnet50": {"arch": "resnet50", "nombre": "ResNet50", "familia": "CNN", "accuracy_test": 0.965},
    "efficientnet_b0": {
        "arch": "efficientnet_b0",
        "nombre": "EfficientNet-B0",
        "familia": "CNN",
        "accuracy_test": 0.895,
    },
    "convnext_tiny": {"arch": "convnext_tiny", "nombre": "ConvNeXt-Tiny", "familia": "CNN", "accuracy_test": 0.930},
    "vit_small": {
        "arch": "vit_small_patch16_224",
        "nombre": "ViT-Small",
        "familia": "Transformer",
        "accuracy_test": 0.974,
    },
    "swin_tiny": {
        "arch": "swin_tiny_patch4_window7_224",
        "nombre": "Swin-Tiny",
        "familia": "Transformer",
        "accuracy_test": 0.974,
    },
}
for _spec in MODELS.values():
    _spec["file"] = f"{_spec['arch']}.pt"

# Ensambles por votación suave, iguales a los de src/ensemble.py. Se promedian las probabilidades dentro de
# cada grupo y luego entre grupos: el híbrido tiene dos grupos y los demás, uno.
_CNN = ["resnet50", "efficientnet_b0", "convnext_tiny"]
_TRANSFORMERS = ["vit_small", "swin_tiny"]
ENSEMBLES = {
    mid: {"nombre": nombre, "familia": "Ensamble", "accuracy_test": accuracy, "grupos": grupos, "reporte": reporte}
    for mid, nombre, accuracy, grupos, reporte in (
        ("ensamble_cnn", "Ensamble de 3 CNN", 0.956, [_CNN], "Homogéneo: 3 CNN"),
        ("ensamble_transformers", "Ensamble de 2 Transformers", 0.974, [_TRANSFORMERS], "Homogéneo: 2 Transformers"),
        ("ensamble_heterogeneo", "Ensamble heterogéneo", 0.965, [_CNN + _TRANSFORMERS], "Heterogéneo: los 5"),
        ("ensamble_hibrido", "Ensamble híbrido", 0.974, [_CNN, _TRANSFORMERS], "Híbrido: CNN + Transformers"),
    )
}
CATALOG = {**MODELS, **ENSEMBLES}  # todo lo que se puede elegir en /predict


class ImageError(Exception):
    """La foto no se puede usar. `status` es el código HTTP que le corresponde."""

    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def shrink(img):
    """Deja el lado corto en 320 px. Es la misma reducción que hizo prepare_data.py con cada foto."""
    img.draft("RGB", (STORE_SIZE * 2, STORE_SIZE * 2))  # JPEG: se decodifica ya reducido (rápido)
    img = ImageOps.exif_transpose(img).convert("RGB")  # las fotos de celular traen la rotación en el EXIF
    scale = STORE_SIZE / min(img.size)
    return img.resize((round(img.width * scale), round(img.height * scale)), Image.Resampling.LANCZOS)


def load_image(data):
    """Bytes de un archivo -> foto reducida. Si no es válida, lanza ImageError con su código HTTP."""
    try:
        img = Image.open(io.BytesIO(data))
        if img.format not in ALLOWED_FORMATS:
            raise ImageError(415, "Tipo de archivo no permitido: usa JPEG, PNG o WebP")
        if img.width * img.height > MAX_PIXELS:
            raise ImageError(413, "La imagen tiene demasiados píxeles")
        if max(img.size) > MAX_ASPECT * min(img.size):
            raise ImageError(400, "Las proporciones de la imagen no son válidas")
        return shrink(img)
    except ImageError:
        raise
    except Image.DecompressionBombError as e:
        raise ImageError(413, "La imagen tiene demasiados píxeles") from e
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as e:  # SyntaxError: PNG/WebP dañados
        raise ImageError(400, "No se pudo abrir la imagen") from e


_EVAL = T.Compose(
    [
        T.CenterCrop(STORE_SIZE),
        T.Resize(IMG_SIZE),
        T.ToImage(),
        T.ToDtype(torch.float32, scale=True),
        T.Normalize(MEAN, STD),
    ]
)  # idéntica a eval_transform() de src/dataset.py


def preprocess(img):
    """Foto reducida -> tensor (1, 3, 224, 224) listo para el modelo."""
    return _EVAL(img).unsqueeze(0)


class Registry:
    """Los modelos entrenados: se cargan la primera vez que se usan (o todos juntos con preload)."""

    def __init__(self, models_dir):
        self.models_dir = Path(models_dir)
        self._loaded = {}
        self._lock = threading.Lock()

    def available(self):
        """Ids de los modelos cuyo archivo de pesos existe."""
        return [mid for mid, spec in MODELS.items() if (self.models_dir / spec["file"]).is_file()]

    def options(self):
        """Los modelos disponibles y los ensambles que tienen los pesos de todos sus integrantes."""
        ids = self.available()
        return ids + [eid for eid, spec in ENSEMBLES.items() if all(m in ids for g in spec["grupos"] for m in g)]

    def get(self, model_id):
        with self._lock:
            if model_id not in self._loaded:
                spec = MODELS[model_id]
                model = timm.create_model(spec["arch"], pretrained=False, num_classes=len(CLASSES))
                # weights_only: solo acepta tensores, nunca ejecuta código del archivo
                state = torch.load(self.models_dir / spec["file"], map_location="cpu", weights_only=True)
                model.load_state_dict(state)
                self._loaded[model_id] = model.eval()
            return self._loaded[model_id]

    def preload(self):
        for model_id in self.available():
            self.get(model_id)

    def predict(self, model_id, batch):
        """Tensor (1, 3, 224, 224) -> resultado con la forma que describe api/CONTRATO.md."""
        groups = ENSEMBLES[model_id]["grupos"] if model_id in ENSEMBLES else [[model_id]]
        loaded = [[self.get(m) for m in group] for group in groups]  # la carga no cuenta como inferencia
        start = time.perf_counter()
        with torch.inference_mode():
            means = [torch.stack([model(batch).softmax(1)[0] for model in group]).mean(0) for group in loaded]
            probs = torch.stack(means).mean(0).tolist()
        ms = round((time.perf_counter() - start) * 1000)
        best = max(range(len(CLASSES)), key=probs.__getitem__)
        return {
            "model": model_id,
            "label": CLASSES[best],
            "confidence": round(probs[best], 4),
            "probabilities": {name: round(p, 4) for name, p in zip(CLASSES, probs, strict=True)},
            "inference_ms": ms,
        }
