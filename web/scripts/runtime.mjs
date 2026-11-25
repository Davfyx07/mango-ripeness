import { access } from "node:fs/promises";
import net from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";

export const webDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
export const repoDir = path.resolve(webDir, "..");
export const python = path.join(
  repoDir,
  ".venv",
  process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
);

export async function requirePython() {
  try {
    await access(python);
  } catch {
    throw new Error(
      "No se encontró .venv. Créalo en la raíz del repositorio antes de iniciar Flask.",
    );
  }
}

function acceptsConnections(port, host) {
  return new Promise((resolve) => {
    const socket = net.createConnection({ port, host });
    socket.setTimeout(300);
    socket.once("connect", () => {
      socket.destroy();
      resolve(true);
    });
    const unavailable = () => {
      socket.destroy();
      resolve(false);
    };
    socket.once("error", unavailable);
    socket.once("timeout", unavailable);
  });
}

export async function portAvailable(port) {
  const listeners = await Promise.all([
    acceptsConnections(port, "127.0.0.1"),
    acceptsConnections(port, "::1"),
  ]);
  if (listeners.some(Boolean)) return false;
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once("error", (error) => {
      if (error.code === "EADDRINUSE") resolve(false);
      else reject(error);
    });
    server.once("listening", () => server.close(() => resolve(true)));
    server.listen(port);
  });
}

export function startBackend() {
  return spawn(
    python,
    ["-m", "flask", "--app", "api.wsgi", "run", "--port", "8000"],
    { cwd: repoDir, stdio: "inherit", env: process.env },
  );
}

export function startFrontend() {
  const vite = path.join(webDir, "node_modules", "vite", "bin", "vite.js");
  return spawn(process.execPath, [vite, "--configLoader", "runner"], {
    cwd: webDir,
    stdio: "inherit",
    env: process.env,
  });
}

export function terminate(child) {
  if (child && child.exitCode === null && !child.killed) child.kill();
}
