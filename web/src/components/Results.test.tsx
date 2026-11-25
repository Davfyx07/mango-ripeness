// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { evaluated, labels } from "../utils/data";
import type { RipenessClass } from "../types/api";
import Results from "./Results";

afterEach(cleanup);

describe("Resultados controlados", () => {
  it.each<RipenessClass>(["unripe", "partially_ripe", "ripe"])(
    "presenta la predicción %s con datos reales del contrato",
    (label) => {
      const reset = vi.fn();
      render(
        <Results
          result={{
            model: "vit_small",
            label,
            confidence: 0.7,
            probabilities: {
              unripe: label === "unripe" ? 0.7 : 0.1,
              partially_ripe: label === "partially_ripe" ? 0.7 : 0.2,
              ripe: label === "ripe" ? 0.7 : 0.1,
            },
            inference_ms: 85,
          }}
          model={evaluated[3]}
          busy={false}
          reset={reset}
          cancel={() => {}}
          hasImage
        />,
      );
      expect(
        screen.getByRole("heading", { name: labels[label] }).classList.contains(label),
      ).toBe(true);
      expect(screen.getAllByText("70%")).toHaveLength(2);
      expect(screen.getByText("ViT-Small")).toBeTruthy();
      expect(screen.getByText("85 ms")).toBeTruthy();
      expect(
        (document.querySelector(`.track .${label}`) as HTMLElement).style.width,
      ).toBe("70%");
      fireEvent.click(screen.getByText(/Analizar otra imagen/));
      expect(reset).toHaveBeenCalledOnce();
    },
  );

  it("permite cancelar un análisis en curso", () => {
    const cancel = vi.fn();
    render(
      <Results
        result={null}
        busy
        reset={() => {}}
        cancel={cancel}
        hasImage
      />,
    );
    fireEvent.click(screen.getByText("Cancelar espera"));
    expect(cancel).toHaveBeenCalledOnce();
  });
});
