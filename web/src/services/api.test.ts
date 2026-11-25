import { afterEach, describe, it, expect, vi } from "vitest";
import { getHealth, getModels, predict, isPrediction, isModel } from "./api";
import { percent } from "../utils/data";
import { validate, checkDimensions } from "../utils/image";
const signal = new AbortController().signal;
const photo = new File([new Uint8Array([255, 216, 255, 224])], "mango.jpg", {
  type: "image/jpeg",
});
const prediction = {
  model: "vit_small",
  label: "ripe",
  probabilities: { unripe: 0.02, partially_ripe: 0.05, ripe: 0.93 },
  confidence: 0.93,
  inference_ms: 85,
};
afterEach(() => vi.unstubAllGlobals());
describe("Contrato Flask", () => {
  it("envía file y model y permite que fetch genere el boundary", async () => {
    const send = vi.fn().mockResolvedValue(Response.json(prediction));
    vi.stubGlobal("fetch", send);
    expect(await predict(photo, "vit_small", signal)).toEqual(prediction);
    const [url, init] = send.mock.calls[0];
    expect(url).toBe("/predict");
    expect(init.method).toBe("POST");
    expect(init.body.get("file").name).toBe(photo.name);
    expect(init.body.get("model")).toBe("vit_small");
    expect(init.headers).toBeUndefined();
  });
  it("admite un servicio activo sin pesos", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(
          Response.json({ status: "ok", models_available: 0 }),
        )
        .mockResolvedValueOnce(Response.json([])),
    );
    expect((await getHealth(signal)).models_available).toBe(0);
    expect(await getModels(signal)).toEqual([]);
  });
  it.each([400, 404, 405, 413, 415, 422, 500, 503])(
    "conserva el código HTTP %s",
    async (status) => {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue(new Response("error", { status })),
      );
      await expect(predict(photo, "vit_small", signal)).rejects.toMatchObject({
        status,
      });
    },
  );
  it("rechaza un éxito sin JSON", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("<html>")));
    await expect(getModels(signal)).rejects.toThrow();
  });
  it("traduce un error de red", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network")));
    await expect(getHealth(signal)).rejects.toMatchObject({
      status: 0,
      message: "No se pudo conectar con el servidor.",
    });
  });
  it("cancela una espera que supera el tiempo límite", async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      "fetch",
      vi.fn(
        (_url, init: RequestInit) =>
          new Promise((_resolve, reject) =>
            init.signal?.addEventListener("abort", () =>
              reject(init.signal?.reason),
            ),
          ),
      ),
    );
    const response = getHealth(new AbortController().signal);
    const assertion = expect(response).rejects.toMatchObject({ status: 408 });
    await vi.advanceTimersByTimeAsync(8_000);
    await assertion;
    vi.useRealTimers();
  });
  it("rechaza una respuesta exitosa con estructura inesperada", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ ok: true })));
    await expect(getHealth(signal)).rejects.toThrow(
      "Respuesta de estado inválida.",
    );
  });
  it("respeta una cancelación solicitada por el usuario", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        (_url, init: RequestInit) =>
          new Promise((_resolve, reject) =>
            init.signal?.addEventListener("abort", () =>
              reject(new DOMException("Aborted", "AbortError")),
            ),
          ),
      ),
    );
    const controller = new AbortController();
    const response = getHealth(controller.signal);
    const assertion = expect(response).rejects.toMatchObject({
      name: "AbortError",
    });
    controller.abort();
    await assertion;
  });
  it("rechaza probabilidades o modelos inválidos", () => {
    expect(isPrediction({ ...prediction, confidence: 2 })).toBe(false);
    expect(isModel({ id: "vit_small" })).toBe(false);
  });
  it("muestra porcentajes en escala 100", () =>
    expect(percent(0.93)).toContain("93"));
});
describe("Validaciones previas", () => {
  it("comprueba la firma independientemente de la extensión", async () => {
    await expect(validate(new File(["texto"], "foto.jpg"))).rejects.toThrow();
    await expect(validate(photo)).resolves.toBeUndefined();
  });
  it("rechaza archivos vacíos", async () =>
    await expect(validate(new File([], "foto.png"))).rejects.toThrow("vacío"));
  it("respeta los límites reales", () => {
    expect(() => checkDimensions(5000, 10000)).not.toThrow();
    expect(() => checkDimensions(5001, 10000)).toThrow();
    expect(() => checkDimensions(801, 100)).toThrow();
  });
});
