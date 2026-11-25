// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import Header from "./Header";

afterEach(cleanup);

function renderHeader(path = "/") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Header />
      <Routes>
        <Route path="*" element={<span>Contenido</span>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("Navegación responsive", () => {
  it("expone el estado accesible del menú móvil", () => {
    renderHeader();
    const button = screen.getByRole("button", { name: "Abrir menú" });
    expect(button.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(button);
    expect(
      screen
        .getByRole("button", { name: "Cerrar menú" })
        .getAttribute("aria-expanded"),
    ).toBe("true");
    expect(screen.getByRole("navigation", { name: "Navegación móvil" })).toBeTruthy();
  });

  it("cierra el menú al navegar", () => {
    renderHeader();
    fireEvent.click(screen.getByRole("button", { name: "Abrir menú" }));
    fireEvent.click(
      screen.getByRole("navigation", { name: "Navegación móvil" }).querySelectorAll("a")[1],
    );
    expect(screen.queryByRole("navigation", { name: "Navegación móvil" })).toBeNull();
  });

  it("cierra con Escape y devuelve el foco al botón", () => {
    renderHeader();
    fireEvent.click(screen.getByRole("button", { name: "Abrir menú" }));
    fireEvent.keyDown(document, { key: "Escape" });
    const button = screen.getByRole("button", { name: "Abrir menú" });
    expect(document.activeElement).toBe(button);
  });
});
