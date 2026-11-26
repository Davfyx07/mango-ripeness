// @vitest-environment jsdom
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getHealth, getModels } from "../services/api";
import { evaluated } from "../utils/data";
import { CONNECTION_RETRY_MS, useService } from "./useService";

vi.mock("../services/api", () => ({
  getHealth: vi.fn(),
  getModels: vi.fn(),
}));

describe("Estado del servicio", () => {
  beforeEach(() => {
    vi.mocked(getHealth).mockReset();
    vi.mocked(getModels).mockReset();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("diferencia un backend conectado sin modelos", async () => {
    vi.mocked(getHealth).mockResolvedValue({
      status: "ok",
      models_available: 0,
    });
    vi.mocked(getModels).mockResolvedValue([]);
    const { result } = renderHook(() => useService());
    await waitFor(() => expect(result.current.status).toBe("empty"));
    expect(result.current.models).toEqual([]);
  });

  it("diferencia un backend desconectado", async () => {
    vi.mocked(getHealth).mockRejectedValue(new Error("network"));
    vi.mocked(getModels).mockRejectedValue(new Error("network"));
    const { result } = renderHook(() => useService());
    await waitFor(() => expect(result.current.status).toBe("offline"));
  });

  it("recupera la conexión automáticamente sin duplicar consultas", async () => {
    vi.useFakeTimers();
    vi.mocked(getHealth)
      .mockRejectedValueOnce(new Error("network"))
      .mockResolvedValue({ status: "ok", models_available: 5 });
    vi.mocked(getModels)
      .mockRejectedValueOnce(new Error("network"))
      .mockResolvedValue(evaluated);
    const { result } = renderHook(() => useService());
    await act(async () => {});
    expect(result.current.status).toBe("offline");
    expect(getHealth).toHaveBeenCalledTimes(1);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(CONNECTION_RETRY_MS);
    });
    expect(result.current.status).toBe("online");
    expect(result.current.models).toEqual(evaluated);
    expect(getHealth).toHaveBeenCalledTimes(2);
    expect(getModels).toHaveBeenCalledTimes(2);
  });

  it("actualiza dinámicamente los modelos con el reintento manual", async () => {
    vi.mocked(getHealth).mockResolvedValue({
      status: "ok",
      models_available: 0,
    });
    vi.mocked(getModels).mockResolvedValueOnce([]).mockResolvedValue(evaluated);
    const { result } = renderHook(() => useService());
    await waitFor(() => expect(result.current.status).toBe("empty"));
    act(() => result.current.reload());
    await waitFor(() => expect(result.current.status).toBe("online"));
    expect(result.current.models).toHaveLength(9);
  });
});
