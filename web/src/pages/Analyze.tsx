import { useEffect, useRef, useState } from "react";
import {
  Upload,
  Camera as CameraIcon,
  Trash2,
  ScanLine,
  ImagePlus,
} from "lucide-react";
import type { Service } from "../hooks/useService";
import { useObjectUrl } from "../hooks/useObjectUrl";
import { accept, checkDimensions, validate } from "../utils/image";
import { percent } from "../utils/data";
import { predict, RequestError } from "../services/api";
import type { PredictionResponse } from "../types/api";
import Camera from "../components/Camera";
import Results from "../components/Results";
export default function Analyze({ service }: { service: Service }) {
  const { models, status, reload } = service;
  const [file, setFile] = useState<File | null>(null),
    [choice, setChoice] = useState<string | null>(null),
    [camera, setCamera] = useState(false),
    [busy, setBusy] = useState(false),
    [checking, setChecking] = useState(false),
    [drag, setDrag] = useState(false),
    [broken, setBroken] = useState(false);
  const [err, setErr] = useState(""),
    [result, setResult] = useState<PredictionResponse | null>(null);
  const input = useRef<HTMLInputElement>(null),
    request = useRef<AbortController | null>(null),
    epoch = useRef(0);
  const selected =
      choice === null ? models[0] : models.find((m) => m.id === choice),
    url = useObjectUrl(file);
  useEffect(
    () => () => {
      epoch.current++;
      request.current?.abort();
    },
    [],
  );
  function invalidate() {
    request.current?.abort();
    request.current = null;
    setBusy(false);
    setResult(null);
    setErr("");
  }
  async function choose(source: File | null | (() => Promise<File>)) {
    const id = ++epoch.current;
    invalidate();
    setFile(null);
    setBroken(false);
    setChecking(!!source);
    if (!source) return;
    try {
      const f = typeof source === "function" ? await source() : source;
      if (epoch.current !== id) return;
      await validate(f);
      if (typeof createImageBitmap === "function") {
        const bitmap = await createImageBitmap(f).catch(() => null);
        if (bitmap) {
          try {
            checkDimensions(bitmap.width, bitmap.height);
          } finally {
            bitmap.close();
          }
        }
      }
      if (epoch.current === id) setFile(f);
    } catch (e) {
      if (id === epoch.current) setErr((e as Error).message);
    } finally {
      if (id === epoch.current) setChecking(false);
    }
  }
  async function analyze() {
    if (
      !file ||
      !selected ||
      status !== "online" ||
      request.current ||
      checking
    )
      return;
    const ctrl = new AbortController();
    request.current = ctrl;
    setBusy(true);
    setResult(null);
    setErr("");
    try {
      const prediction = await predict(file, selected.id, ctrl.signal);
      if (!ctrl.signal.aborted) setResult(prediction);
    } catch (e) {
      if (ctrl.signal.aborted) return;
      setErr((e as Error).message);
      if (e instanceof RequestError && [404, 503].includes(e.status)) {
        setChoice("");
        reload();
      }
    } finally {
      if (request.current === ctrl) {
        request.current = null;
        setBusy(false);
      }
    }
  }
  return (
    <main className="wrap page analysis">
      <h1>Analizar mango</h1>
      <p className="intro">
        Elige una fotografía y un modelo para evaluar su maduración.
      </p>
      <div className="analysis-grid">
        <section className="panel">
          <h2>Fotografía del mango</h2>
          <input
            className="sr-only"
            tabIndex={-1}
            aria-label="Archivo de imagen"
            ref={input}
            type="file"
            accept={accept}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void choose(f);
              e.target.value = "";
            }}
          />
          <div
            className={"drop " + (drag ? "drag" : "")}
            onDragOver={(e) => {
              e.preventDefault();
              if (!busy) setDrag(true);
            }}
            onDragLeave={() => setDrag(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDrag(false);
              if (!busy && e.dataTransfer.files[0])
                void choose(e.dataTransfer.files[0]);
            }}
          >
            {file ? (
              <>
                {url && !broken ? (
                  <img
                    src={url}
                    alt="Mango seleccionado"
                    onError={() => setBroken(true)}
                    onLoad={(e) => {
                      try {
                        checkDimensions(
                          e.currentTarget.naturalWidth,
                          e.currentTarget.naturalHeight,
                        );
                      } catch (ex) {
                        void choose(null);
                        setErr((ex as Error).message);
                      }
                    }}
                  />
                ) : (
                  <p>Vista previa no disponible en este navegador.</p>
                )}
                <strong>{file.name}</strong>
                <small>
                  {(file.size / 1024).toLocaleString("es-CO", {
                    maximumFractionDigits: 0,
                  })}{" "}
                  KB
                </small>
              </>
            ) : (
              <>
                <ImagePlus />
                <strong>
                  {checking ? "Verificando imagen…" : "Arrastra tu imagen aquí"}
                </strong>
                <small>JPEG, PNG, WebP o MPO · Hasta 25 MB por solicitud</small>
              </>
            )}
          </div>
          <div className="actions photo-actions">
            <button disabled={busy} onClick={() => input.current?.click()}>
              <Upload />
              {file ? "Cambiar imagen" : "Subir imagen"}
            </button>
            <button disabled={busy} onClick={() => setCamera(true)}>
              <CameraIcon />
              Tomar fotografía
            </button>
            {file && (
              <button
                className="icon"
                disabled={busy}
                onClick={() => void choose(null)}
                aria-label="Eliminar imagen"
              >
                <Trash2 />
              </button>
            )}
          </div>
          <details className="samples">
            <summary>Usar una fotografía de ejemplo</summary>
            <div className="sample-list">
              {Object.entries({verde:"Verde", ambar:"En maduración", maduro:"Maduro"}).map(([name,label]) =>
                <button key={name} disabled={busy} onClick={() => void choose(async () => {
                  const response = await fetch("/" + name + ".jpg");
                  if (!response.ok) throw new Error("No se pudo abrir el ejemplo. Inténtalo de nuevo.");
                  return new File([await response.blob()], name + ".jpg", {type:"image/jpeg"});
                })}><img src={"/" + name + ".jpg"} alt="" />{label}</button>
              )}
            </div>
          </details>
          <label htmlFor="model">Modelo de inteligencia artificial</label>
          <select
            id="model"
            value={selected?.id ?? ""}
            disabled={busy || status !== "online"}
            onChange={(e) => {
              invalidate();
              setChoice(e.target.value);
            }}
          >
            <option value="" disabled>
              Selecciona un modelo
            </option>
            {models.map((m) => (
              <option value={m.id} key={m.id}>
                {m.nombre} · {m.familia}
              </option>
            ))}
          </select>
          {selected && (
            <p className="hint">
              Precisión experimental en estudio:{" "}
              {percent(selected.accuracy_test)}.
            </p>
          )}
          {status !== "online" && (
            <p role="status">
              {
                {
                  loading: "Cargando modelos…",
                  offline: "Servidor desconectado.",
                  empty: "Servidor conectado, sin modelos disponibles.",
                  error: "No se pudo obtener la lista de modelos.",
                }[status]
              }{" "}
              {status !== "loading" && (
                <button onClick={reload}>Reintentar</button>
              )}
            </p>
          )}
          {err && (
            <p className="error" role="alert">
              {err}
            </p>
          )}
          <button
            className="primary wide"
            disabled={
              !file || !selected || busy || checking || status !== "online"
            }
            onClick={analyze}
          >
            <ScanLine />
            Analizar mango
          </button>
        </section>
        <Results
          hasImage={!!file}
          result={result}
          model={selected}
          busy={busy}
          reset={() => void choose(null)}
          cancel={invalidate}
        />
      </div>
      <p className="notice">
        Los modelos se entrenaron con fotos de estudio y clasifican cualquier
        imagen, incluso si no contiene un mango.
      </p>
      {camera && (
        <Camera
          onClose={() => setCamera(false)}
          onConfirm={(f) => {
            setCamera(false);
            void choose(f);
          }}
        />
      )}
    </main>
  );
}
