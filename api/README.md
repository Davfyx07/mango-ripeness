# Backend: API del portal de madurez del mango

Servidor **Flask** que recibe la foto de un mango, la prepara exactamente como se prepararon las fotos de entrenamiento, la pasa por el modelo que se elija (uno de los 5 entrenados) y devuelve la madurez: `unripe`, `partially_ripe` o `ripe`, con las tres probabilidades.

| Documento | Para quién |
|---|---|
| **Este archivo** | Quien mantiene el backend: cómo se organiza, se enciende, se prueba y se despliega |
| [`CONTRATO.md`](CONTRATO.md) | Todos: las rutas, lo que reciben y lo que devuelven |
| [`CONECTAR_FRONT.md`](CONECTAR_FRONT.md) | Quien hace la interfaz: cómo conectarse desde cualquier lenguaje o framework |

## Cómo está organizado

```
api/
├─ app.py            las rutas de Flask (/health, /models, /predict) y el manejo de errores
├─ inference.py      preprocesamiento, carga de los modelos y predicción. No depende de Flask
├─ wsgi.py           punto de entrada para producción (gunicorn)
├─ models/           los 5 archivos .pt entrenados (NO están en git)
├─ tests/            pruebas automáticas
├─ Dockerfile        imagen para desplegar
├─ requirements.txt  librerías del servidor
└─ requirements-dev.txt  más las de pruebas
```

La interfaz la hace otra persona en `web/`. Cuando haya una (su `index.html`, o la compilada en `web/dist/`), el backend la sirve en `/`; mientras tanto `/` responde 404.

## Poner el backend a funcionar

Desde la **raíz del repositorio**, con Python 3.13:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install torch==2.14.1 torchvision==0.29.1 --index-url https://download.pytorch.org/whl/cpu
pip install -r api/requirements.txt
```

Después hay que **poner los pesos entrenados** en `api/models/`. Están en `outputs_ddp\models\` del PC donde se entrenó:

```powershell
copy outputs_ddp\models\*.pt api\models\
```

Son 5 archivos de unos 420 MB en total, con estos nombres (los de `timm`): `resnet50.pt`, `efficientnet_b0.pt`, `convnext_tiny.pt`, `vit_small_patch16_224.pt` y `swin_tiny_patch4_window7_224.pt`. No se suben a git. Si falta alguno, ese modelo simplemente no aparece en `/models`.

Encender (desarrollo):

```powershell
flask --app api.wsgi run --port 8000
```

Comprobar: abrir `http://localhost:8000/health` (debe decir `models_available: 5`).

En Linux o en un contenedor se usa **gunicorn**: `gunicorn api.wsgi:app --bind 0.0.0.0:8000 --workers 1 --threads 2 --timeout 120`. No corre en Windows.

## Variables de entorno (todas opcionales)

| Variable | Por defecto | Qué hace |
|---|---|---|
| `MANGO_MODELS_DIR` | `api/models` | Carpeta con los `.pt` |
| `MANGO_CORS_ORIGINS` | `localhost` en los puertos `5173` y `3000` | Orígenes de la interfaz que pueden llamar a la API, separados por coma |
| `MANGO_PRELOAD` | `1` | Con `1`, gunicorn carga los 5 modelos al arrancar (la primera petición no espera) |
| `PORT` | `8000` | Puerto en el contenedor (lo define Cloud Run) |

## Lo más importante que hay que saber

**El preprocesamiento debe ser idéntico al del entrenamiento.** Es lo que más puede fallar y no da ningún error: el modelo simplemente acierta menos. Los pasos, en `inference.py`: corregir la rotación EXIF, pasar a RGB, dejar el lado corto en 320 px (LANCZOS), recorte central de 320, reducir a 224 y normalizar con la media y desviación de ImageNet. Las pruebas comprueban que el resultado es **idéntico, bit a bit,** al de `src/dataset.py`.

**Otras decisiones de diseño:**

- **El formato se detecta por el contenido** y no por el nombre ni por el `Content-Type` que declare el cliente. Se aceptan JPEG, PNG, WebP y MPO (el JPEG con varias imágenes que usan muchas cámaras y celulares; sin esto se rechazaban fotos reales).
- **Límites:** 25 MB por archivo, 50 millones de píxeles (evita "bombas de descompresión", como un PNG de 64 megapíxeles que pesa 100 KB) y proporciones de hasta 8 a 1 (una tira de 20×4000 px reducida a 320 px de ancho pediría gigas de memoria).
- **Los pesos se cargan con `weights_only=True`:** el archivo solo puede contener tensores, nunca código.
- **El id del modelo nunca se usa para armar rutas:** solo se acepta uno de la lista fija.
- **Los errores internos devuelven un mensaje genérico;** el detalle queda solo en el registro del servidor.
- **No se guardan las fotos.** Se procesan en memoria.
- **Un solo proceso con 2 hilos** en producción: los 5 modelos ocupan unos 2 GB de RAM y un proceso por núcleo los duplicaría.

## Pruebas

```powershell
pip install -r api/requirements-dev.txt
pytest api/tests --cov=api
```

| Qué se prueba | Dónde |
|---|---|
| El preprocesamiento es idéntico al del entrenamiento, rota las fotos de celular, rechaza archivos dañados, formatos no permitidos, bombas de descompresión y proporciones absurdas | `test_inference.py` |
| Las 3 rutas con los 5 modelos, todos los códigos de error, CORS, concurrencia (16 peticiones a la vez), la interfaz servida, errores internos sin filtrar detalles y que `CONTRATO.md` coincida con el código | `test_api.py` |
| **Con los modelos entrenados de verdad:** las 114 fotos de test por la API dan la precisión que midió el entrenamiento, y una foto original de 24 MP da lo mismo que su copia reducida | `test_real_models.py` (solo si están los `.pt` y las fotos; se omite sola en GitHub Actions) |

Las pruebas normales usan **pesos aleatorios** con las arquitecturas reales (`tests/make_random_weights.py`), así que corren en cualquier lado sin los `.pt`. Para correr solo las de los modelos entrenados: `pytest api/tests -m real_models`. Cobertura actual: 100 %.

## GitHub Actions

`.github/workflows/backend-ci.yml` corre en cada Pull Request hacia `main` y en cada push a `main` o `backend`:

| Trabajo | Qué comprueba |
|---|---|
| **Estilo y seguridad** | `ruff` (errores, imports, formato) y `bandit` (vulnerabilidades en el código) |
| **Vulnerabilidades en las librerías** | `pip-audit` sobre `requirements.txt` |
| **Pruebas** | Toda la batería, con cobertura mínima del 90 % |
| **Contenedor de punta a punta** | Construye la imagen de Docker, la enciende con pesos aleatorios y llama a `/health`, `/models`, a `/predict` con una foto real del repo para cada uno de los 5 modelos, y a los códigos de error |

## Desplegar

El contenedor funciona en cualquier lado que ejecute Docker. Desde la raíz, con los `.pt` ya en `api/models/`:

```powershell
docker build -f api/Dockerfile -t mango-api .
docker run -p 8000:8000 mango-api
```

- **Memoria:** pide **al menos 2 GB** de RAM (4 GB para ir holgado).
- **Cloud Run:** `gcloud run deploy mango --source . --memory 4Gi --port 8000` (usa `$PORT` solo).
- **Un VPS:** `docker run -d --restart unless-stopped -p 8000:8000 mango-api` y un proxy con HTTPS delante (por ejemplo Caddy). **La cámara del navegador exige HTTPS.**
- **AWS Lambda** necesitaría un adaptador y una imagen de contenedor, y tendría arranques en frío de varios segundos al cargar los modelos. No es lo más cómodo para este servicio.
- La imagen **incluye los `.pt`** si están en `api/models/` al construirla; por eso `.dockerignore` deja pasar solo `api/` y `web/`.

## Lo que este backend NO hace (todavía)

- **No limita cuántas peticiones puede hacer cada visitante.** Para una demo con enlace público conviene ponerlo detrás de un servicio que lo haga, o añadir `flask-limiter`.
- **No detecta si la foto es de un mango.** El modelo clasifica cualquier imagen.
- **No guarda fotos ni resultados.**
- **No tiene autenticación.** Cualquiera con el enlace puede usarlo.

## Si algo falla

| Síntoma | Causa probable |
|---|---|
| `/models` devuelve `[]` y `/predict` da `503` | No están los `.pt` en `api/models/`, o `MANGO_MODELS_DIR` apunta a otra carpeta |
| `415` con fotos reales | Un formato que no es JPEG, PNG, WebP ni MPO (por ejemplo HEIC) |
| La interfaz dice que no hay conexión, pero el servidor está encendido | CORS: el origen de la interfaz no está en `MANGO_CORS_ORIGINS` |
| La cámara en vivo no abre en el celular | Falta HTTPS (solo funciona en `localhost` y con HTTPS) |
| El servidor tarda muchos segundos en la primera foto | Está cargando los modelos: usar `MANGO_PRELOAD=1` |
