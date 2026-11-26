import {
  classes,
  type HealthResponse,
  type ModelInfo,
  type PredictionResponse,
} from "../types/api";
const base = (import.meta.env.VITE_API_URL || "").trim().replace(/\/+$/, "");
const record = (x: unknown): x is Record<string, unknown> =>
  !!x && typeof x === "object";
const probability = (x: unknown): x is number =>
  typeof x === "number" && x >= 0 && x <= 1;
export const isHealth = (x: unknown): x is HealthResponse =>
  record(x) &&
  x.status === "ok" &&
  Number.isInteger(x.models_available) &&
  Number(x.models_available) >= 0;
export const isModel = (x: unknown): x is ModelInfo =>
  record(x) &&
  typeof x.id === "string" &&
  !!x.id &&
  typeof x.nombre === "string" &&
  ["CNN", "Transformer", "Ensamble"].includes(String(x.familia)) &&
  probability(x.accuracy_test);
export function isPrediction(x: unknown): x is PredictionResponse {
  if (!record(x) || !record(x.probabilities)) return false;
  const p = x.probabilities;
  return (
    typeof x.model === "string" &&
    classes.some((k) => x.label === k) &&
    classes.every((k) => probability(p[k])) &&
    probability(x.confidence) &&
    Number.isInteger(x.inference_ms) &&
    Number(x.inference_ms) >= 0
  );
}
const messages: Record<number, string> = {
  400: "La imagen está dañada o tiene proporciones inadecuadas.",
  404: "El modelo o la ruta ya no está disponible.",
  405: "El servidor rechazó el método de la solicitud.",
  413: "La imagen supera el límite de peso o píxeles.",
  415: "Usa una imagen JPEG, PNG, WebP o MPO.",
  422: "Selecciona una imagen y un modelo.",
  500: "El servidor encontró un problema. Inténtalo de nuevo.",
  503: "Actualmente no hay modelos disponibles.",
};
export class RequestError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}
async function request(
  path: string,
  options: RequestInit,
  timeoutMs: number,
): Promise<unknown> {
  const timeout = new AbortController();
  const timer = globalThis.setTimeout(
    () => timeout.abort(new DOMException("Timeout", "TimeoutError")),
    timeoutMs,
  );
  const abort = () => timeout.abort(options.signal?.reason);
  options.signal?.addEventListener("abort", abort, { once: true });
  let response: Response;
  try {
    response = await fetch(base + path, { ...options, signal: timeout.signal });
  } catch (e) {
    if (options.signal?.aborted) throw e;
    if (timeout.signal.aborted)
      throw new RequestError(
        "El servidor tardó demasiado en responder. Inténtalo de nuevo.",
        408,
      );
    throw new RequestError("No se pudo conectar con el servidor.", 0);
  } finally {
    globalThis.clearTimeout(timer);
    options.signal?.removeEventListener("abort", abort);
  }
  const data: unknown = await response.json().catch(() => null);
  if (!response.ok)
    throw new RequestError(
      messages[response.status] ?? "La solicitud no pudo completarse.",
      response.status,
    );
  return data;
}
export async function getHealth(signal: AbortSignal) {
  const x = await request("/health", { signal }, 8_000);
  if (!isHealth(x)) throw Error("Respuesta de estado inválida.");
  return x;
}
export async function getModels(signal: AbortSignal) {
  const x = await request("/models", { signal }, 8_000);
  if (!Array.isArray(x) || !x.every(isModel))
    throw Error("Listado de modelos inválido.");
  return x as ModelInfo[];
}
export async function predict(file: File, model: string, signal: AbortSignal) {
  const body = new FormData();
  body.append("file", file);
  body.append("model", model);
  const x = await request(
    "/predict",
    { method: "POST", body, signal },
    120_000,
  );
  if (!isPrediction(x) || x.model !== model)
    throw Error("El servidor devolvió un resultado inesperado.");
  return x;
}
