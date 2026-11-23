"""Con los modelos ENTRENADOS de verdad. Se omite sola si no están (como en GitHub Actions).

Comprueba que servir un modelo por la API da la misma precisión que midió el entrenamiento:
si el preprocesamiento del servidor se desviara del del entrenamiento, aquí se vería.
Para correrlas: copiar los .pt a api/models/ (ver api/README.md) y  pytest api/tests -m real_models
"""

import csv

import pytest

from api.app import create_app
from api.inference import MODELS
from api.tests.helpers import REPO, post_predict

MODELS_DIR = REPO / "api" / "models"
TEST_CSV = REPO / "Data" / "splits" / "test.csv"
HAVE_WEIGHTS = all((MODELS_DIR / spec["file"]).is_file() for spec in MODELS.values())

pytestmark = pytest.mark.skipif(not HAVE_WEIGHTS, reason="faltan los .pt entrenados en api/models/")


@pytest.fixture(scope="module")
def real_client():
    return create_app(models_dir=MODELS_DIR, web_dir=None).test_client()


def _test_split():
    with open(TEST_CSV, encoding="utf-8") as f:
        return list(csv.DictReader(f))


@pytest.mark.real_models
@pytest.mark.parametrize("model", list(MODELS))
def test_served_accuracy_matches_training_report(real_client, model):
    """Las 114 fotos de test, una por una por la API, contra la precisión del resultado guardado."""
    rows = _test_split()
    hits = 0
    for row in rows:
        data = (REPO / "Data" / "processed" / row["file"]).read_bytes()
        body = post_predict(real_client, data, model=model).get_json()
        hits += body["label"] == row["label"]
    accuracy = hits / len(rows)
    # 0.03 = 3 fotos: margen por float16 en GPU (entrenamiento) contra float32 en CPU (servidor)
    assert accuracy == pytest.approx(MODELS[model]["accuracy_test"], abs=0.03), f"{model}: {accuracy:.3f}"


@pytest.mark.real_models
@pytest.mark.raw_photos
def test_full_resolution_originals_give_same_answers_as_reduced_copies(real_client):
    """Una foto original de 24 MP (como la de un celular) debe dar lo mismo que su copia reducida del entrenamiento."""
    raw_dirs = {p.name.lower(): p for p in (REPO / "Data" / "raw").iterdir() if p.is_dir()}
    rows = _test_split()[::6]  # 19 fotos repartidas
    same = 0
    for row in rows:
        stem = row["file"].split("/")[1].removesuffix(".jpg")
        original = raw_dirs[row["label"]] / f"{stem}.JPG"
        a = post_predict(real_client, original.read_bytes(), model="vit_small").get_json()["label"]
        b = post_predict(
            real_client, (REPO / "Data" / "processed" / row["file"]).read_bytes(), model="vit_small"
        ).get_json()["label"]
        same += a == b
    assert same / len(rows) >= 0.9, f"coinciden {same} de {len(rows)}"
