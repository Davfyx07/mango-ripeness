"""La API completa: rutas, errores, seguridad, CORS, concurrencia y que el contrato escrito sea el real."""

import csv
import importlib
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor

import pytest
from PIL import Image

from api.app import create_app, find_web_dir
from api.inference import CLASSES, MODELS
from api.tests.helpers import REPO, make_image, make_pil, post_predict, to_bytes

MODEL_IDS = list(MODELS)


# --------------------------------------------------------------------------- /health y /models
def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.get_json() == {"status": "ok", "models_available": 5}


def test_models_lists_the_five(client):
    data = client.get("/models").get_json()
    assert [m["id"] for m in data] == MODEL_IDS
    for m in data:
        assert set(m) == {"id", "nombre", "familia", "accuracy_test"}
        assert m["familia"] in ("CNN", "Transformer")
        assert 0 < m["accuracy_test"] <= 1
    assert sum(m["familia"] == "CNN" for m in data) == 3
    assert sum(m["familia"] == "Transformer" for m in data) == 2


def test_models_only_lists_models_with_weights(tmp_path):
    client = create_app(models_dir=tmp_path, web_dir=None).test_client()
    assert client.get("/models").get_json() == []
    assert client.get("/health").get_json()["models_available"] == 0


# --------------------------------------------------------------------------- /predict: caso correcto
@pytest.mark.parametrize("model", MODEL_IDS)
def test_predict_every_model(client, model):
    res = post_predict(client, make_image(), model=model)
    assert res.status_code == 200
    body = res.get_json()
    assert set(body) == {"model", "label", "confidence", "probabilities", "inference_ms"}
    assert body["model"] == model
    assert body["label"] in CLASSES
    assert list(body["probabilities"]) == CLASSES
    assert sum(body["probabilities"].values()) == pytest.approx(1, abs=1e-3)
    assert body["confidence"] == max(body["probabilities"].values())
    assert body["probabilities"][body["label"]] == body["confidence"]
    assert isinstance(body["inference_ms"], int) and body["inference_ms"] >= 0


def test_predict_is_deterministic(client):
    a = post_predict(client, make_image()).get_json()
    b = post_predict(client, make_image()).get_json()
    assert a["probabilities"] == b["probabilities"]


@pytest.mark.parametrize(("fmt", "name", "mime"), [("PNG", "f.png", "image/png"), ("WEBP", "f.webp", "image/webp")])
def test_predict_png_and_webp(client, fmt, name, mime):
    assert post_predict(client, make_image(fmt), filename=name, content_type=mime).status_code == 200


def test_predict_ignores_file_name_and_declared_type(client):
    """El formato sale del contenido: un PNG que se hace pasar por .txt se acepta, y un .jpg falso se rechaza."""
    assert post_predict(client, make_image("PNG"), filename="x.txt", content_type="text/plain").status_code == 200
    fake = post_predict(client, b"<html>no soy una imagen</html>", filename="x.jpg", content_type="image/jpeg")
    assert fake.status_code == 400


def test_phone_photo_with_exif_rotation_gives_same_answer_as_upright(client):
    base = make_pil((640, 480))
    rotated = post_predict(client, to_bytes(base, "PNG", orientation=6), filename="a.png", content_type="image/png")
    upright = post_predict(client, to_bytes(base.transpose(Image.Transpose.ROTATE_270), "PNG"), filename="b.png")
    assert rotated.get_json()["probabilities"] == upright.get_json()["probabilities"]


def test_large_phone_sized_photo(client):
    res = post_predict(client, make_image(size=(4032, 3024)))  # 12 megapíxeles, como un celular
    assert res.status_code == 200


def test_predict_response_is_not_cached(client):
    res = post_predict(client, make_image())
    assert res.headers["Cache-Control"] == "no-store"
    assert res.headers["X-Content-Type-Options"] == "nosniff"


# --------------------------------------------------------------------------- /predict: errores
def test_missing_fields_422(client):
    assert client.post("/predict", data={"model": "vit_small"}).status_code == 422
    assert post_predict(client, make_image(), model="").status_code == 422
    assert client.post("/predict").status_code == 422
    assert "detail" in client.post("/predict").get_json()


def test_unknown_model_404(client):
    res = post_predict(client, make_image(), model="gpt-5")
    assert res.status_code == 404
    assert "gpt-5" in res.get_json()["detail"]


@pytest.mark.parametrize("bad", ["../../etc/passwd", "resnet50.pt", "vit_small_patch16_224", "RESNET50", " resnet50"])
def test_model_id_is_not_a_path(client, bad):
    """El id solo puede ser uno de la lista: nunca se usa para armar rutas de archivos."""
    assert post_predict(client, make_image(), model=bad).status_code == 404


def test_no_weights_503(tmp_path):
    client = create_app(models_dir=tmp_path, web_dir=None).test_client()
    assert post_predict(client, make_image()).status_code == 503


def test_empty_file_400(client):
    assert post_predict(client, b"").status_code == 400


def test_corrupt_image_400(client):
    data = make_image()
    assert post_predict(client, data[: len(data) // 2]).status_code == 400


def test_gif_415(client):
    assert post_predict(client, make_image("GIF"), filename="a.gif", content_type="image/gif").status_code == 415


@pytest.mark.filterwarnings("ignore::PIL.Image.DecompressionBombWarning")
def test_too_many_pixels_413(client):
    data = to_bytes(Image.new("L", (8000, 8000)), "PNG")
    assert post_predict(client, data, filename="a.png", content_type="image/png").status_code == 413


def test_upload_over_limit_413(weights_dir):
    client = create_app(models_dir=weights_dir, web_dir=None, max_upload_mb=1).test_client()
    res = post_predict(client, os.urandom(2 * 1024 * 1024))
    assert res.status_code == 413
    assert "1 MB" in res.get_json()["detail"]


def test_unknown_route_and_wrong_method_are_json(client):
    nf, bad = client.get("/nada"), client.get("/predict")
    assert (nf.status_code, bad.status_code) == (404, 405)
    assert "detail" in nf.get_json() and "detail" in bad.get_json()


def test_internal_errors_do_not_leak_details(app):
    """Si algo revienta por dentro, el cliente recibe un mensaje genérico, nunca la excepción."""
    registry = app.extensions["registry"]
    original = registry.predict
    registry.predict = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("SECRETO /ruta/interna"))
    try:
        res = post_predict(app.test_client(), make_image())
    finally:
        registry.predict = original
    assert res.status_code == 500
    assert res.get_json() == {"detail": "Error interno del servidor"}
    assert "SECRETO" not in res.get_data(as_text=True)


# --------------------------------------------------------------------------- CORS
def test_cors_allows_dev_origin_and_blocks_others(client):
    ok = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert ok.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"
    evil = client.get("/health", headers={"Origin": "https://sitio-malo.example"})
    assert "Access-Control-Allow-Origin" not in evil.headers


def test_cors_preflight(client):
    res = client.options(
        "/predict", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"}
    )
    assert res.status_code == 200
    assert res.headers["Access-Control-Allow-Origin"] == "http://localhost:3000"
    assert "POST" in res.headers["Access-Control-Allow-Methods"]


def test_cors_origins_come_from_environment(weights_dir, monkeypatch):
    monkeypatch.setenv("MANGO_CORS_ORIGINS", "https://mi-demo.example, https://otra.example")
    client = create_app(models_dir=weights_dir, web_dir=None).test_client()
    assert client.get("/health", headers={"Origin": "https://mi-demo.example"}).headers["Access-Control-Allow-Origin"]
    assert (
        "Access-Control-Allow-Origin" not in client.get("/health", headers={"Origin": "http://localhost:5173"}).headers
    )


# --------------------------------------------------------------------------- concurrencia
def test_concurrent_requests_all_succeed_with_same_answer(app):
    data = make_image()

    def call(_):
        return post_predict(app.test_client(), data, model="efficientnet_b0")

    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(call, range(16)))
    assert {r.status_code for r in results} == {200}
    assert len({json.dumps(r.get_json()["probabilities"]) for r in results}) == 1


# --------------------------------------------------------------------------- interfaz servida por el mismo servidor
def test_serves_web_folder(weights_dir, tmp_path):
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<h1>Mango</h1>")
    (web / "app.js").write_text("console.log(1)")
    (tmp_path / "secreto.txt").write_text("no debe salir")
    client = create_app(models_dir=weights_dir, web_dir=web).test_client()
    assert b"<h1>Mango</h1>" in client.get("/").data
    assert client.get("/app.js").status_code == 200
    assert client.get("/../secreto.txt").status_code == 404
    assert client.get("/%2e%2e/secreto.txt").status_code == 404
    assert client.get("/health").get_json()["status"] == "ok"  # la API tiene prioridad sobre los archivos
    assert client.get("/predict").status_code == 405  # y /predict sigue diciendo que solo acepta POST


def test_no_web_folder_means_no_root_route(client):
    assert client.get("/").status_code == 404


# --------------------------------------------------------------------------- wsgi (producción)
def test_wsgi_preloads_all_models(weights_dir, monkeypatch):
    monkeypatch.setenv("MANGO_MODELS_DIR", str(weights_dir))
    monkeypatch.setenv("MANGO_PRELOAD", "1")
    import api.wsgi

    wsgi = importlib.reload(api.wsgi)
    assert len(wsgi.app.extensions["registry"]._loaded) == 5


# --------------------------------------------------------------------------- el contrato escrito == el código
def _contract():
    return (REPO / "api" / "CONTRATO.md").read_text(encoding="utf-8")


def test_contract_example_lists_the_same_models_as_the_code():
    block = re.search(r"## `GET /models`.*?```json\n(.*?)```", _contract(), re.S).group(1)
    documented = json.loads(block)
    assert [m["id"] for m in documented] == MODEL_IDS
    for m in documented:
        assert m["nombre"] == MODELS[m["id"]]["nombre"]
        assert m["accuracy_test"] == MODELS[m["id"]]["accuracy_test"]


def test_contract_documents_every_route_and_error_code(app):
    doc = _contract()
    for rule in app.url_map.iter_rules():
        if rule.endpoint != "static":
            assert rule.rule in doc, f"{rule.rule} no está en CONTRATO.md"
    for code in (400, 404, 413, 415, 422, 503):
        assert f"`{code}`" in doc, f"el error {code} no está en CONTRATO.md"


def test_accuracy_shown_to_users_matches_the_reported_results():
    """Los números del selector salen de los resultados del entrenamiento: no se inventan ni se desactualizan."""
    with open(REPO / "results" / "v0.2_dos_pc" / "ensemble_results.csv", encoding="utf-8") as f:
        reported = {row["modelo"]: float(row["accuracy"]) for row in csv.DictReader(f)}
    for spec in MODELS.values():
        assert round(reported[spec["arch"]], 3) == spec["accuracy_test"]


def test_find_web_dir_prefers_dist_then_web_then_none(tmp_path, monkeypatch):
    monkeypatch.setattr("api.app.ROOT", tmp_path)
    assert find_web_dir() is None
    (tmp_path / "web").mkdir()
    (tmp_path / "web" / "index.html").write_text("web")
    assert find_web_dir() == tmp_path / "web"
    (tmp_path / "web" / "dist").mkdir()
    (tmp_path / "web" / "dist" / "index.html").write_text("dist")
    assert find_web_dir() == tmp_path / "web" / "dist"
