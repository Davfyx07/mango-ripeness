# Contrato de la API

Este archivo es lo que une al backend (`api/`) con la interfaz (`web/`). Quien haga la interfaz puede trabajar solo con esto, sin esperar al backend: las respuestas de ejemplo son las que va a devolver.

- **Dirección en desarrollo:** `http://localhost:8000`
- **Cómo conectarse desde cualquier lenguaje o framework:** [`CONECTAR_FRONT.md`](CONECTAR_FRONT.md)
- **Formato:** JSON. Los errores tienen la forma `{"detail": "mensaje"}`.

## `GET /health`

¿Está vivo el servidor?

```json
{"status": "ok"}
```

## `GET /models`

La lista para llenar el selector. Son **5 modelos**.

```json
[
  {"id": "resnet50",        "nombre": "ResNet50",        "familia": "CNN",         "accuracy_test": 0.965},
  {"id": "efficientnet_b0", "nombre": "EfficientNet-B0", "familia": "CNN",         "accuracy_test": 0.895},
  {"id": "convnext_tiny",   "nombre": "ConvNeXt-Tiny",   "familia": "CNN",         "accuracy_test": 0.930},
  {"id": "vit_small",       "nombre": "ViT-Small",       "familia": "Transformer", "accuracy_test": 0.974},
  {"id": "swin_tiny",       "nombre": "Swin-Tiny",       "familia": "Transformer", "accuracy_test": 0.974}
]
```

`accuracy_test` se midió en 114 fotos de estudio (resultados en `results/v0.2_dos_pc/`). **No es la precisión que tendrá con fotos de celular**: conviene mostrarlo con ese aviso.

## `POST /predict`

Clasifica una foto. Se envía como **multipart/form-data** con dos campos:

| Campo | Qué es |
|---|---|
| `file` | La imagen: JPEG, PNG o WebP, de hasta **25 MB** |
| `model` | El `id` de un modelo de `/models` |

Respuesta correcta (`200`):

```json
{
  "model": "vit_small",
  "label": "ripe",
  "confidence": 0.93,
  "probabilities": {"unripe": 0.02, "partially_ripe": 0.05, "ripe": 0.93},
  "inference_ms": 85
}
```

- `label` es siempre uno de `unripe`, `partially_ripe` o `ripe`. Para mostrarlo en español, una propuesta: `unripe` = "Verde", `partially_ripe` = "En maduración", `ripe` = "Madura".
- `confidence` es la probabilidad más alta. Las tres `probabilities` suman 1.

### Errores

| Código | Cuándo |
|---|---|
| `400` | La imagen no se pudo abrir (archivo dañado, vacío, no es una imagen) o tiene proporciones absurdas (más de 8 veces más larga que ancha) |
| `404` | El `model` no existe (o no es uno de los ids de `/models`) |
| `413` | La imagen pesa más de 25 MB, o tiene más de 50 millones de píxeles |
| `415` | El tipo de archivo no es JPEG, PNG ni WebP (se detecta por el contenido, no por el nombre) |
| `422` | Falta el campo `file` o `model` |
| `503` | El servidor no tiene ningún modelo cargado (problema de despliegue, no de la foto) |
| `500` | Error interno. El mensaje es siempre genérico: `{"detail": "Error interno del servidor"}` |

`/health` responde además `models_available` (cuántos modelos hay cargados):

```json
{"status": "ok", "models_available": 5}
```

## Cosas que la interfaz debe saber

- **El modelo clasifica cualquier foto.** Si le suben una cara o un paisaje, igual devolverá `ripe`, `unripe` o `partially_ripe`, a veces con mucha seguridad. No puede decir "esto no es un mango". Conviene un aviso en la página y mostrar las tres probabilidades, no solo la ganadora.
- Fue entrenado con **fotos de estudio** (un mango, fondo liso, buena luz). Con fotos de celular en otro ambiente puede fallar más.
- Las fotos tardan **entre 0.1 y 0.3 segundos** en el servidor (medido en una laptop). La primera petición después de arrancar puede tardar más.
- Las fotos de iPhone pueden venir en HEIC. Los navegadores suelen convertirlas a JPEG al subirlas desde un `<input type="file">`; si no, hay que convertirlas antes de enviar.
- La interfaz **no debe guardar ni mostrar nada que no sea de la respuesta**: el servidor no conserva las fotos.
