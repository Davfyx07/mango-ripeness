# Cómo conectar la interfaz con el backend

Guía para quien haga la interfaz, **en el lenguaje o framework que elija**. La API es HTTP normal con JSON: cualquier cosa que pueda enviar un formulario sirve. El detalle de cada ruta está en [`CONTRATO.md`](CONTRATO.md).

Lo que la interfaz tiene que hacer es solo esto:

1. Pedir la lista de modelos y mostrarla en un **selector**.
2. Conseguir una foto: **tomarla con la cámara** o **elegirla de la galería o del equipo**.
3. Enviarla con el modelo elegido y **mostrar la respuesta**.

## 1. Encender el backend

Desde la raíz del repositorio (los pasos completos están en [`README.md`](README.md)):

```powershell
.venv\Scripts\Activate.ps1
flask --app api.wsgi run --port 8000
```

Comprueba que funciona abriendo `http://localhost:8000/health` (debe decir `models_available: 5`). Sin los `.pt` entrenados el servidor enciende igual, pero `/models` sale vacío y `/predict` da `503`.

## 2. Probar la API sin escribir código

```bash
curl http://localhost:8000/health
curl http://localhost:8000/models
curl -F "file=@foto.jpg" -F "model=vit_small" http://localhost:8000/predict
```

En **Postman**: método POST a `/predict`, pestaña *Body* → *form-data*, un campo `model` (tipo Text) y un campo `file` (tipo File).

## 3. Lo esencial: la llamada

Es un `multipart/form-data` con dos campos: `file` (la imagen) y `model` (un `id` de `/models`).

```js
const form = new FormData();
form.append("file", blobOArchivo, "foto.jpg");
form.append("model", "vit_small");
const res = await fetch("http://localhost:8000/predict", { method: "POST", body: form });
const data = await res.json();
// res.ok -> { model, label, confidence, probabilities: {unripe, partially_ripe, ripe}, inference_ms }
// !res.ok -> { detail: "mensaje" }  (res.status: 400, 404, 413, 415, 422, 503)
```

**Errores típicos al empezar:**

- **No pongas `Content-Type` a mano.** El navegador lo agrega con el separador correcto. Si lo pones, el servidor responde `422`.
- El campo se llama **`file`**, no `image` ni `foto`.
- Si la interfaz corre en otro puerto que la API (por ejemplo `5173` o `3000`), el backend ya permite esos orígenes. Para otro origen, se define al encender el servidor: `MANGO_CORS_ORIGINS=https://mi-sitio.com`.

## 4. La cámara y la galería

Hay **dos formas** de conseguir la foto. Se pueden usar las dos.

### Opción A: la más simple y la que menos falla (recomendada para empezar)

Un campo de archivo. En el celular, `capture` abre la **cámara nativa**; sin `capture`, abre la galería. En el computador, los dos abren el selector de archivos.

```html
<input type="file" accept="image/*" id="galeria">                       <!-- galería o equipo -->
<input type="file" accept="image/*" capture="environment" id="camara">  <!-- cámara trasera del celular -->
```

No necesita permisos ni HTTPS.

### Opción B: cámara en vivo, con vista previa y botón "Tomar foto"

```js
const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false });
video.srcObject = stream;                       // <video autoplay playsinline muted>

// al pulsar "Tomar foto":
const canvas = document.createElement("canvas");
canvas.width = video.videoWidth;
canvas.height = video.videoHeight;
canvas.getContext("2d").drawImage(video, 0, 0);
canvas.toBlob((blob) => enviar(blob), "image/jpeg", 0.92);
stream.getTracks().forEach((t) => t.stop());    // apaga la cámara al terminar
```

**Importante:** `getUserMedia` **solo funciona en HTTPS o en `localhost`**. Si abres la página desde el celular con la IP del computador (`http://192.168.1.5:8000`), el navegador bloquea la cámara en vivo. Para probar desde el celular, usa un túnel con HTTPS (por ejemplo `cloudflared tunnel --url http://localhost:8000`) o la opción A. En producción, con HTTPS, funciona normal.

### Reducir la foto antes de subirla (recomendado)

Una foto de celular puede pesar varios MB. El servidor acepta hasta 25 MB y la reduce él mismo, pero subir una versión de 1600 px de lado largo es mucho más rápido y no cambia el resultado:

```js
async function reducir(file, maxLado = 1600) {
  const bmp = await createImageBitmap(file, { imageOrientation: "from-image" });  // respeta la rotación de la foto
  const k = Math.min(1, maxLado / Math.max(bmp.width, bmp.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bmp.width * k);
  canvas.height = Math.round(bmp.height * k);
  canvas.getContext("2d").drawImage(bmp, 0, 0, canvas.width, canvas.height);
  return new Promise((ok) => canvas.toBlob(ok, "image/jpeg", 0.92));
}
```

Las fotos HEIC (algunos iPhone) no las abre el navegador con `createImageBitmap` en todos los casos. Safari las convierte a JPEG al subirlas desde un `<input type="file">`; si no, hay que mostrar un mensaje.

## 5. Qué mostrar

- **Selector:** `nombre`, `familia` y `accuracy_test` de cada modelo de `/models`.
- **Resultado:** la clase ganadora, su `confidence` en porcentaje y **las tres probabilidades** (barras o similar).
- Etiquetas en español, una propuesta: `unripe` = "Verde", `partially_ripe` = "En maduración", `ripe` = "Madura".
- **Aviso visible:** los modelos se entrenaron con fotos de estudio y clasifican cualquier imagen, aunque no sea un mango. Una confianza baja (por ejemplo menos de 60 %) conviene marcarla como poco fiable.
- **Mensajes por error:** `413` "muy pesada", `415` "usa JPEG, PNG o WebP", `400` "no se pudo abrir", y un mensaje de "no se pudo conectar" si `fetch` falla.
- **Seguridad:** muestra el texto del servidor con `textContent`, no con `innerHTML`.
- El botón "Analizar" debe quedar **deshabilitado mientras espera la respuesta** (puede tardar un segundo, y la primera vez más).

## 6. Ejemplos por tecnología

La llamada es la misma en todas: un POST multipart a `/predict`. Cambia solo cómo se escribe.

### React (Vite)

```jsx
import { useEffect, useState } from "react";

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export default function Mango() {
  const [modelos, setModelos] = useState([]);
  const [modelo, setModelo] = useState("");
  const [archivo, setArchivo] = useState(null);
  const [resultado, setResultado] = useState(null);
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(false);

  useEffect(() => {
    fetch(`${API}/models`).then((r) => r.json()).then((m) => { setModelos(m); setModelo(m[0]?.id ?? ""); })
      .catch(() => setError("No se pudo cargar la lista de modelos"));
  }, []);

  async function analizar() {
    setCargando(true); setError(""); setResultado(null);
    const form = new FormData();
    form.append("file", archivo);
    form.append("model", modelo);
    try {
      const res = await fetch(`${API}/predict`, { method: "POST", body: form });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail);
      setResultado(data);
    } catch (e) {
      setError(e.message || "No se pudo conectar con el servidor");
    } finally {
      setCargando(false);
    }
  }

  return (
    <div>
      <select value={modelo} onChange={(e) => setModelo(e.target.value)}>
        {modelos.map((m) => <option key={m.id} value={m.id}>{m.nombre} ({m.familia})</option>)}
      </select>
      {/* capture abre la cámara en el celular; quítalo para la galería */}
      <input type="file" accept="image/*" capture="environment" onChange={(e) => setArchivo(e.target.files[0])} />
      <button onClick={analizar} disabled={!archivo || cargando}>Analizar</button>
      {error && <p role="alert">{error}</p>}
      {resultado && <pre>{JSON.stringify(resultado.probabilities, null, 2)}</pre>}
    </div>
  );
}
```

En Vite, la dirección de la API se define en un archivo `.env` con `VITE_API_URL=http://localhost:8000`.

### Next.js

Es el mismo código de React, con dos cuidados:

- El componente que usa la cámara o `FormData` debe ser de cliente (`"use client"` al inicio del archivo). La cámara no existe en el servidor.
- La dirección va en `NEXT_PUBLIC_API_URL`. Si se despliega junto al backend como un solo servicio, usa la **exportación estática** (`output: "export"` en `next.config.js`) y deja la carpeta generada en `web/`. Con renderizado en servidor haría falta un segundo servicio.

### Vue 3

```vue
<script setup>
import { ref, onMounted } from "vue";
const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const modelos = ref([]), modelo = ref(""), archivo = ref(null), resultado = ref(null);

onMounted(async () => { modelos.value = await (await fetch(`${API}/models`)).json(); modelo.value = modelos.value[0]?.id; });

async function analizar() {
  const form = new FormData();
  form.append("file", archivo.value);
  form.append("model", modelo.value);
  resultado.value = await (await fetch(`${API}/predict`, { method: "POST", body: form })).json();
}
</script>

<template>
  <select v-model="modelo"><option v-for="m in modelos" :key="m.id" :value="m.id">{{ m.nombre }}</option></select>
  <input type="file" accept="image/*" capture="environment" @change="archivo = $event.target.files[0]" />
  <button :disabled="!archivo" @click="analizar">Analizar</button>
  <pre v-if="resultado">{{ resultado }}</pre>
</template>
```

### Flutter (Dart)

Con los paquetes `http` e `image_picker`:

```dart
final foto = await ImagePicker().pickImage(source: ImageSource.camera); // o ImageSource.gallery
final req = http.MultipartRequest('POST', Uri.parse('$api/predict'))
  ..fields['model'] = 'vit_small'
  ..files.add(await http.MultipartFile.fromPath('file', foto!.path));
final res = await http.Response.fromStream(await req.send());
final data = jsonDecode(utf8.decode(res.bodyBytes));
```

En un emulador de Android, `localhost` del computador es `http://10.0.2.2:8000`.

### Android nativo (Kotlin, OkHttp)

```kotlin
val body = MultipartBody.Builder().setType(MultipartBody.FORM)
    .addFormDataPart("model", "vit_small")
    .addFormDataPart("file", "foto.jpg", file.asRequestBody("image/jpeg".toMediaType()))
    .build()
val request = Request.Builder().url("$api/predict").post(body).build()
client.newCall(request).execute().use { println(it.body!!.string()) }
```

### Python (para probar scripts)

```python
import requests

with open("foto.jpg", "rb") as f:
    r = requests.post("http://localhost:8000/predict", files={"file": f}, data={"model": "vit_small"})
print(r.status_code, r.json())
```

## 7. Cuando la interfaz esté lista

Dos formas de dejarla funcionando junto al backend:

- **Un solo servicio (la más simple):** compilar la interfaz y dejar el resultado en `web/dist/` (o su `index.html` directamente en `web/`). El backend la sirve en `/`. Mismo origen, sin CORS, y la cámara funciona en cuanto haya HTTPS.
- **Dos servicios:** la interfaz en su propio sitio y el backend aparte. En ese caso hay que decirle al backend el origen de la interfaz con `MANGO_CORS_ORIGINS`, y la interfaz debe usar la dirección pública del backend en vez de `localhost`.

## Preguntas frecuentes

**¿Por qué responde `422`?** Falta el campo `file` o `model`, o se puso `Content-Type` a mano.

**¿Por qué la primera foto tarda más?** El servidor puede estar cargando los modelos. Con `MANGO_PRELOAD=1` (lo normal en producción) los carga al encender.

**¿Se guardan las fotos?** No. El servidor las procesa en memoria y no conserva nada.

**¿Puedo elegir cualquier modelo?** Los que devuelve `/models`. Los cinco están entrenados con las mismas fotos, y la tabla de `accuracy_test` ayuda a mostrar cuál va mejor.
