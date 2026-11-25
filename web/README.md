# MangoVision AI

Frontend de clasificación visual de mangos construido con React, TypeScript estricto, Vite, Tailwind, Lucide, Motion y HashRouter. La interfaz consume exclusivamente `GET /health`, `GET /models` y `POST /predict` del backend Flask.

## Obtener el proyecto

```powershell
git clone <URL_DEL_REPOSITORIO>
cd mango-ripeness
git switch feature/frontend
cd web
npm ci
```

Si el repositorio ya existe, actualízalo siguiendo el flujo Git acordado por el equipo y comprueba que la rama activa sea `feature/frontend`.

## Requisitos

- Node.js 24 y npm.
- Python 3.13 para reproducir exactamente el entorno documentado por el backend.
- Aproximadamente 2 GB de RAM para cargar los cinco modelos en CPU.
- Los pesos entrenados para realizar predicciones reales.

El entorno local ligero usado durante el desarrollo emplea Python 3.11.9, PyTorch 2.13.0 CPU y torchvision 0.28.0 CPU mediante un entorno creado con `--system-site-packages`. El entorno oficial documentado usa Python 3.13, PyTorch 2.14.1 y torchvision 0.29.1 CPU. CUDA no es necesaria para ejecutar la API local.

## Preparar el backend

Desde la raíz del repositorio, para reproducir el entorno oficial:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install torch==2.14.1 torchvision==0.29.1 --index-url https://download.pytorch.org/whl/cpu
pip install -r api\requirements.txt
```

En Linux o macOS, activa el entorno con `source .venv/bin/activate`. Para reutilizar una instalación CPU compatible de PyTorch sin duplicarla:

```powershell
python -m venv --system-site-packages .venv
.\.venv\Scripts\python.exe -m pip install -r api\requirements.txt
```

Comprueba todas las importaciones desde `web/`:

```powershell
npm run backend:check
```

## Incorporar los pesos

Copia a `api/models/` los cinco archivos proporcionados por el responsable del entrenamiento:

```text
resnet50.pt
efficientnet_b0.pt
convnext_tiny.pt
vit_small_patch16_224.pt
swin_tiny_patch4_window7_224.pt
```

Los pesos no deben subirse a GitHub desde esta rama. Si están en otra carpeta, configura su ruta antes de iniciar Flask:

```powershell
$env:MANGO_MODELS_DIR="D:\modelos\mango"
```

En Linux o macOS:

```bash
export MANGO_MODELS_DIR="/ruta/modelos/mango"
```

Reinicia Flask después de añadir, reemplazar o cambiar la ubicación de los pesos. `/models` anuncia dinámicamente solo los archivos disponibles.

## Iniciar los servicios

En una terminal, desde `web/`:

```powershell
npm run backend
```

En otra terminal:

```powershell
npm run dev
```

También puedes iniciar ambos procesos desde `web/`:

```powershell
npm run dev:all
```

Los scripts resuelven `.venv` de forma relativa, comprueban los puertos 8000 y 5173, no cierran procesos ajenos y terminan los procesos que ellos iniciaron al recibir Ctrl+C. Son compatibles con Windows, Linux y macOS.

Abre `http://localhost:5173/#/`. El proxy de Vite reenvía exclusivamente `/health`, `/models` y `/predict` a `http://127.0.0.1:8000`. Para un backend remoto, copia `.env.example` a `.env.local`, define `VITE_API_URL` y reinicia Vite. Las variables `VITE_*` son públicas y no deben contener secretos.

Comprueba la comunicación directa y mediante proxy:

```powershell
npm run check:api
```

Sin pesos, `/health` debe devolver `models_available: 0`, `/models` debe devolver `[]` y la interfaz mostrará que el servidor está conectado sin modelos. Puedes seleccionar, previsualizar y eliminar imágenes, pero el análisis permanecerá deshabilitado.

## Ejecutar una predicción

Con al menos un modelo anunciado por `/models`, abre `/#/analizar`, selecciona o captura una imagen, elige un modelo y pulsa **Analizar mango**. La solicitud envía `file` y `model` como multipart. El navegador genera automáticamente el encabezado `Content-Type`.

Se aceptan JPEG, PNG, WebP y MPO. La petición completa debe ocupar menos de 25 MB, la imagen no puede superar 50 millones de píxeles y su proporción máxima es 8:1.

## Cámara

La cámara en vivo usa `getUserMedia` sin audio y requiere `localhost` o HTTPS. Una dirección IP local servida por HTTP no constituye un contexto seguro. El selector nativo de archivos permanece disponible cuando el navegador no admite cámara en vivo. La validación final debe incluir un dispositivo físico, permisos reales y cambio entre cámaras.

## Pruebas y compilación

Desde `web/`:

```powershell
npm run lint
npm run test
npm run build
npm run preview
```

`npm run build` valida TypeScript estricto y genera `web/dist/`. Los mocks de respuestas exitosas existen únicamente dentro de las pruebas y nunca se cargan en la aplicación.

## Servir el frontend desde Flask

Genera primero el build con `npm run build`. Deja `VITE_API_URL` vacío para usar rutas relativas y después inicia Flask desde la raíz:

```powershell
.\.venv\Scripts\python.exe -m flask --app api.wsgi run --port 8000
```

Flask detectará `web/dist/index.html` y servirá:

```text
http://localhost:8000/#/
http://localhost:8000/#/analizar
http://localhost:8000/#/modelos
```

HashRouter permite recargar cualquiera de estas secciones sin requerir fallback adicional. Las rutas de API conservan prioridad sobre los archivos estáticos.

## Recursos y procedencia

Las fotografías de referencia proceden de las copias reducidas del dataset *Alphonso Mango Ripening Stage Classification Dataset*, Akshatha Prabhu (2024), [Mendeley Data](https://doi.org/10.17632/tyghd6gxw2.1), bajo [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Los originales usados son `Data/processed/unripe/1004(7).jpg`, `Data/processed/partially_ripe/1058(4).jpg` y `Data/processed/ripe/288(7).jpg`.

Las precisiones experimentales proceden de `results/v0.2_dos_pc/ensemble_results.csv` y fueron calculadas sobre 114 fotografías de estudio. La confianza mostrada después de un análisis corresponde exclusivamente a esa predicción.
