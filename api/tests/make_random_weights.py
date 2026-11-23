"""Genera pesos ALEATORIOS con las arquitecturas reales, para probar la API sin los .pt entrenados.

Uso (desde la raíz del repo):  python -m api.tests.make_random_weights <carpeta>
Sirve para los tests y para la prueba del contenedor en GitHub Actions. Las predicciones no significan nada.
"""

import sys
from pathlib import Path

import timm
import torch

from api.inference import CLASSES, MODELS


def make_weights(folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    for i, spec in enumerate(MODELS.values()):
        torch.manual_seed(i)  # siempre los mismos pesos aleatorios
        model = timm.create_model(spec["arch"], pretrained=False, num_classes=len(CLASSES))
        torch.save(model.state_dict(), folder / spec["file"])
    return folder


if __name__ == "__main__":
    print("pesos aleatorios en", make_weights(sys.argv[1]))
