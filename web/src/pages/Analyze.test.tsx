// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useState } from "react";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import Analyze from "./Analyze";
import { predict } from "../services/api";
import { evaluated } from "../utils/data";
import Camera from "../components/Camera";
vi.mock("../services/api", async (original) => ({
  ...(await original<typeof import("../services/api")>()),
  predict: vi.fn(),
}));
vi.mock("../utils/image", async (original) => ({
  ...(await original<typeof import("../utils/image")>()),
  validate: vi.fn().mockResolvedValue(undefined),
}));
const online = {
  status: "online" as const,
  models: evaluated,
  reload: vi.fn(),
};
beforeEach(() => {
  URL.createObjectURL = vi.fn(() => "blob:preview");
  URL.revokeObjectURL = vi.fn();
});
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});
describe("Flujo de análisis", () => {
  it.each([["Verde","verde"],["En maduración","ambar"],["Maduro","maduro"]])("envía el ejemplo %s solo después de confirmar", async (label,name) => {
    const load = vi.fn().mockResolvedValue({ok:true,blob:async()=>new Blob(["imagen"],{type:"image/jpeg"})});
    vi.stubGlobal("fetch",load);
    vi.mocked(predict).mockResolvedValueOnce({model:"resnet50",label:"unripe",confidence:.8,probabilities:{unripe:.8,partially_ripe:.1,ripe:.1},inference_ms:12});
    render(<Analyze service={online}/>);
    fireEvent.click(screen.getByText("Usar una fotografía de ejemplo"));
    fireEvent.click(screen.getByRole("button",{name:label}));
    await screen.findByText(name+".jpg");
    expect(load).toHaveBeenCalledWith("/"+name+".jpg");
    expect(predict).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button",{name:"Analizar mango"}));
    await screen.findByText("12 ms");
    const file = vi.mocked(predict).mock.calls[0][0];
    expect(file).toBeInstanceOf(File);
    expect(file.name).toBe(name+".jpg");
    expect(screen.getByRole("heading",{name:"Verde"})).toBeTruthy();
  });
  it("distingue el servidor conectado sin pesos y permite reintentar", () => {
    render(<Analyze service={{ ...online, status: "empty", models: [] }} />);
    expect(screen.getByRole("status").textContent).toContain("sin modelos");
    expect(
      (
        screen.getByRole("button", {
          name: "Analizar mango",
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(true);
    fireEvent.click(screen.getByText("Reintentar"));
    expect(online.reload).toHaveBeenCalledOnce();
  });
  it("permite preparar y eliminar una imagen aunque no haya modelos", async () => {
    render(<Analyze service={{ ...online, status: "empty", models: [] }} />);
    fireEvent.change(screen.getByLabelText("Archivo de imagen"), {
      target: {
        files: [new File(["jpeg"], "sin-modelos.jpg", { type: "image/jpeg" })],
      },
    });
    await screen.findByText("sin-modelos.jpg");
    expect(
      (screen.getByRole("button", { name: "Analizar mango" }) as HTMLButtonElement)
        .disabled,
    ).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Eliminar imagen" }));
    expect(screen.queryByText("sin-modelos.jpg")).toBeNull();
    expect(URL.revokeObjectURL).toHaveBeenCalled();
  });
  it("espera confirmación y limpia el resultado al cambiar de modelo", async () => {
    vi.mocked(predict).mockResolvedValueOnce({
      model: "resnet50",
      label: "ripe",
      confidence: 0.93,
      probabilities: { ripe: 0.93, unripe: 0.02, partially_ripe: 0.05 },
      inference_ms: 85,
    });
    render(<Analyze service={online} />);
    const file = new File(["jpeg"], "mi-mango.jpg", { type: "image/jpeg" });
    fireEvent.change(screen.getByLabelText("Archivo de imagen"), {
      target: { files: [file] },
    });
    await screen.findByText("mi-mango.jpg");
    expect(predict).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Analizar mango" }));
    await screen.findByText("85 ms");
    expect(predict).toHaveBeenCalledWith(file, "resnet50", expect.anything());
    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "vit_small" },
    });
    expect(screen.queryByText("85 ms")).toBeNull();
  });
  it("impide peticiones duplicadas mientras el análisis sigue en curso", async () => {
    vi.mocked(predict).mockImplementation(() => new Promise(() => {}));
    render(<Analyze service={online} />);
    fireEvent.change(screen.getByLabelText("Archivo de imagen"), {
      target: {
        files: [new File(["jpeg"], "mango.jpg", { type: "image/jpeg" })],
      },
    });
    await screen.findByText("mango.jpg");
    const analyze = screen.getByRole("button", { name: "Analizar mango" });
    fireEvent.click(analyze);
    fireEvent.click(analyze);
    expect(predict).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByText("Cancelar espera"));
    expect((analyze as HTMLButtonElement).disabled).toBe(false);
  });
  it("descarta una respuesta tardía después de reemplazar la imagen", async () => {
    let finish!: (value: Awaited<ReturnType<typeof predict>>) => void;
    vi.mocked(predict).mockImplementation(
      () => new Promise((resolve) => (finish = resolve)),
    );
    render(<Analyze service={online} />);
    fireEvent.change(screen.getByLabelText("Archivo de imagen"), {
      target: { files: [new File(["a"], "primera.jpg")] },
    });
    await screen.findByText("primera.jpg");
    fireEvent.click(screen.getByRole("button", { name: "Analizar mango" }));
    fireEvent.change(screen.getByLabelText("Archivo de imagen"), {
      target: { files: [new File(["b"], "segunda.jpg")] },
    });
    await screen.findByText("segunda.jpg");
    finish({
      model: "resnet50",
      label: "ripe",
      confidence: 0.9,
      probabilities: { unripe: 0.05, partially_ripe: 0.05, ripe: 0.9 },
      inference_ms: 40,
    });
    await act(async () => {});
    expect(screen.queryByText("40 ms")).toBeNull();
  });
  it("muestra un error de predicción y desbloquea la interfaz", async () => {
    vi.mocked(predict).mockRejectedValueOnce(
      new Error("Actualmente no hay modelos disponibles."),
    );
    render(<Analyze service={online} />);
    fireEvent.change(screen.getByLabelText("Archivo de imagen"), {
      target: { files: [new File(["a"], "mango.jpg")] },
    });
    await screen.findByText("mango.jpg");
    fireEvent.click(screen.getByRole("button", { name: "Analizar mango" }));
    await screen.findByRole("alert");
    expect(screen.getByRole("alert").textContent).toContain(
      "no hay modelos disponibles",
    );
    expect(
      (screen.getByRole("button", { name: "Analizar mango" }) as HTMLButtonElement)
        .disabled,
    ).toBe(false);
  });
  it("detiene permisos tardíos al salir de la cámara", async () => {
    let grant!: (s: MediaStream) => void;
    const stop = vi.fn();
    Object.defineProperty(HTMLDialogElement.prototype, "showModal", {
      value: vi.fn(),
      configurable: true,
    });
    vi.stubGlobal("isSecureContext", true);
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {
        getUserMedia: vi.fn(
          () =>
            new Promise<MediaStream>((resolve) => {
              grant = resolve;
            }),
        ),
      },
    });
    const view = render(<Camera onClose={() => {}} onConfirm={() => {}} />);
    view.unmount();
    grant({ getTracks: () => [{ stop }] } as unknown as MediaStream);
    await waitFor(() => expect(stop).toHaveBeenCalledOnce());
  });
  it("libera la cámara activa al cerrar el diálogo", async () => {
    const stop = vi.fn();
    Object.defineProperty(HTMLDialogElement.prototype, "showModal", {
      value: vi.fn(),
      configurable: true,
    });
    vi.stubGlobal("isSecureContext", true);
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {
        getUserMedia: vi.fn().mockResolvedValue({
          getTracks: () => [{ stop }],
        }),
        enumerateDevices: vi.fn().mockResolvedValue([]),
      },
    });
    function CameraHost() {
      const [open, setOpen] = useState(true);
      return open ? (
        <Camera onClose={() => setOpen(false)} onConfirm={() => {}} />
      ) : null;
    }
    render(<CameraHost />);
    await waitFor(() => expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalled());
    fireEvent.click(
      screen.getByRole("button", { name: "Cerrar cámara", hidden: true }),
    );
    await waitFor(() => expect(stop).toHaveBeenCalledOnce());
  });
});
