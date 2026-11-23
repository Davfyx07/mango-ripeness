# Interfaz web

Esta carpeta es para la interfaz del portal: una página donde se sube la foto de un mango, se elige uno de los 5 modelos y se ve la predicción.

**Empieza por [`../api/CONECTAR_FRONT.md`](../api/CONECTAR_FRONT.md)**: cómo conectarte desde cualquier lenguaje o framework, con la cámara, la galería y ejemplos en React, Vue, Next.js, Flutter y Kotlin. Las rutas y respuestas exactas están en [`../api/CONTRATO.md`](../api/CONTRATO.md).

**Ya hay una interfaz de ejemplo que funciona: [`index.html`](index.html).** Con el backend encendido se ve en `http://localhost:8000/`. Reemplázala por la tuya, o úsala de referencia.

## Qué debe poder hacer

1. Cargar la lista de modelos con `GET /models` y mostrarla como selector.
2. Dejar subir una foto, o tomarla con la cámara del celular.
3. Enviarla con `POST /predict` y mostrar la clase y las **tres probabilidades**.
4. Mostrar un aviso de que fue entrenado con fotos de estudio y que no detecta si la foto no es un mango.
5. Manejar los errores del contrato (foto muy pesada, tipo no permitido, servidor caído).

## Ejemplo de la llamada

```js
const form = new FormData();
form.append("file", archivo);          // un File del <input type="file">
form.append("model", "vit_small");     // un id de /models
const res = await fetch("http://localhost:8000/predict", { method: "POST", body: form });
const data = await res.json();         // { label, confidence, probabilities, ... }
```

No pongas `Content-Type` a mano: el navegador lo pone con el separador correcto.

## Con qué tecnología hacerla

Cualquiera sirve, porque la API no depende de la interfaz. Lo que sí conviene saber:

- **Recomendado: React con Vite, o HTML y JavaScript puros.** Se compilan a archivos estáticos que el mismo backend puede servir, y así todo se despliega como un solo servicio.
- **Next.js complica el despliegue** si usa renderizado en el servidor, porque necesita un servidor de Node aparte. Si lo prefieren, que use la exportación estática (`output: "export"`), que genera archivos estáticos igual que Vite.

## Desarrollo local

La interfaz corre en su propio puerto (por ejemplo `5173` con Vite) y la API en `8000`. El backend permitirá esos orígenes (CORS) en desarrollo.

Cuando la interfaz esté lista, el resultado compilado (por ejemplo `dist/`) se deja en esta carpeta para que el backend lo sirva.
